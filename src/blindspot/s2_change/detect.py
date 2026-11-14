"""S2 change detection: stack.nc -> change.nc, patches.geojson, timeseries.json.

Two methods, chosen with --method:

* omnibus  (default) sequential omnibus test on HH+HV at a set false-alarm rate,
           then a persistence check on the HV log-ratio.
* logratio (fallback) HV log-ratio against the reference-date mean, normalised per
           date by the scene median, thresholded at -3 dB or at the noise tail.

Run:  python -m blindspot.s2_change.detect [--method logratio] [--threshold -3]
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from .. import config as C
from ..grid import pixel_area_ha, to_db, transform_from_coords
from .omnibus import first_change


def boxcar(a: np.ndarray, size: int) -> np.ndarray:
    """Mean filter over the last two axes, ignoring NaN."""
    from scipy.ndimage import uniform_filter

    if size <= 1:
        return a
    valid = np.isfinite(a)
    num = uniform_filter(np.where(valid, a, 0.0), size=(1, size, size) if a.ndim == 3 else size)
    den = uniform_filter(valid.astype(float), size=(1, size, size) if a.ndim == 3 else size)
    with np.errstate(invalid="ignore", divide="ignore"):
        return num / den


def normalised_logratio(hv: np.ndarray, times: list[str], water: np.ndarray, smooth: int = 3) -> np.ndarray:
    """HV log-ratio (dB) of each date against the reference mean, with each date's scene median removed.

    Removing the per-date median cancels scene-wide shifts from rain, soil moisture and
    calibration jumps (layer 2 of the uncertainty model). WS2: replace the scene median
    by the median over a stable-forest polygon once one is drawn.
    """
    ref_idx = [i for i, t in enumerate(times) if t in C.REFERENCE_DATES]
    hv_s = boxcar(hv, smooth)
    ref = np.nanmean(hv_s[ref_idx], axis=0)
    lr = to_db(hv_s / ref[None])
    land = water == 0
    for t in range(lr.shape[0]):
        lr[t] -= np.nanmedian(lr[t][land])
    lr[:, ~land] = np.nan
    return lr


def normalise_scene(a: np.ndarray, times: list[str], water: np.ndarray) -> np.ndarray:
    """Scale each date so its median ratio to the reference mean over land is 1."""
    ref_idx = [i for i, t in enumerate(times) if t in C.REFERENCE_DATES]
    ref = np.nanmean(a[ref_idx], axis=0)
    land = water == 0
    out = a.copy()
    for t in range(a.shape[0]):
        with np.errstate(invalid="ignore", divide="ignore"):
            out[t] /= np.nanmedian((a[t] / ref)[land])
    return out


def estimate_enl(a: np.ndarray, times: list[str], water: np.ndarray) -> float:
    """Median over land pixels of mean^2/variance across the reference dates."""
    ref_idx = [i for i, t in enumerate(times) if t in C.REFERENCE_DATES]
    r = a[ref_idx][:, water == 0]
    with np.errstate(invalid="ignore", divide="ignore"):
        enl = np.nanmean(r, 0) ** 2 / np.nanvar(r, 0, ddof=1)
    return float(np.nanmedian(enl))


def persistent(mask_t: np.ndarray, n: int) -> np.ndarray:
    """True at date t where mask holds on dates t..t+n-1."""
    out = mask_t.copy()
    for s in range(1, n):
        shifted = np.zeros_like(mask_t)
        shifted[:-s] = mask_t[s:]
        out &= shifted
    return out


def detect_arrays(hh, hv, water, times, enl, method="omnibus",
                  threshold=C.PARAMS["logratio_threshold_db"], alpha=C.PARAMS["omnibus_alpha"], smooth=3):
    """Core detector on in-memory arrays. Returns (first_change_index, p_value, logratio_db, description).

    Kept separate from file I/O so the synthetic burn test can call it directly.
    """
    lr = normalised_logratio(hv, times, water, smooth)
    ncons = C.PARAMS["min_consecutive_dates"]
    if method == "logratio":
        if threshold == "auto":
            # noise tail: 1st percentile of the reference-date ratios
            ref_idx = [i for i, t in enumerate(times) if t in C.REFERENCE_DATES]
            threshold = float(np.nanpercentile(lr[ref_idx], 1))
        below = lr < float(threshold)
        ok = persistent(below, ncons)
        first = np.where(ok.any(0), ok.argmax(0), -1).astype("int16")
        pval = np.full(first.shape, np.nan, "float32")
        desc = f"logratio threshold {float(threshold):.2f} dB, {ncons} consecutive dates, boxcar {smooth}"
    else:
        # Radiometric normalisation (uncertainty layer 2): divide each date by its scene-median
        # ratio to the reference, per band, so rain, soil moisture and calibration jumps that
        # shift the whole scene are not read as change by the omnibus test.
        hh_s, hv_s = normalise_scene(boxcar(hh, smooth), times, water), normalise_scene(boxcar(hv, smooth), times, water)
        # Effective looks after smoothing, measured from the data instead of assumed:
        # over the reference dates (no change expected) ENL = mean^2 / variance per pixel.
        enl_eff = estimate_enl(hv_s, times, water)
        idx, pval, _ = first_change(np.nan_to_num(hh_s, nan=1e-6), np.nan_to_num(hv_s, nan=1e-6), enl_eff, alpha)
        # persistence: HV must stay at least 1 dB below reference for ncons dates from the change
        below = persistent(lr < -1.0, ncons)
        first = np.full(idx.shape, -1, "int16")
        for t in range(1, len(times)):
            first[(idx == t) & below[t]] = t
        desc = f"sequential omnibus alpha {alpha}, ENL_eff {enl_eff:.1f}, HV persists below -1 dB for {ncons} dates"
    first[water != 0] = -1
    return first, pval, lr, desc


def run(method: str = "omnibus", threshold: float | str = C.PARAMS["logratio_threshold_db"],
        alpha: float = C.PARAMS["omnibus_alpha"], smooth: int = 3):
    import xarray as xr

    ds = xr.open_dataset(C.INTERIM / "stack.nc")
    times = [str(t)[:10] for t in ds.time.values]
    hh, hv = ds.hh.values.astype("float64"), ds.hv.values.astype("float64")
    water = ds.water.values
    first, pval, lr, desc = detect_arrays(hh, hv, water, times, ds.attrs["enl"], method, threshold, alpha, smooth)
    changed = first >= 0
    n_changed = np.where(changed, np.sum(lr < -1.0, axis=0), 0).astype("int16")
    import warnings
    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore", RuntimeWarning)
        min_lr = np.nanmin(lr, axis=0).astype("float32")

    out = xr.Dataset(
        {"changed": (("y", "x"), changed.astype("uint8")),
         "first_change": (("y", "x"), first),
         "n_changed": (("y", "x"), n_changed),
         "min_logratio_db": (("y", "x"), min_lr),
         "p_value": (("y", "x"), pval)},
        coords={"y": ds.y, "x": ds.x},
        attrs={"crs": C.CRS, "method": desc, "dates": ",".join(times), "fixture": int(ds.attrs.get("fixture", 0))},
    )
    C.INTERIM.mkdir(parents=True, exist_ok=True)
    out.to_netcdf(C.INTERIM / "change.nc")
    make_patches(out, ds, lr, times)
    print(f"[S2] {desc}: {changed.sum()} changed pixels")


def make_patches(ch, ds, lr, times):
    from pyproj import Transformer
    from rasterio.features import shapes
    from scipy.ndimage import label
    import shapely
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union

    changed = ch.changed.values.astype(bool)
    first = ch.first_change.values
    lab, n = label(changed, structure=np.ones((3, 3)))
    px_ha = pixel_area_ha()
    min_px = int(np.ceil(C.PARAMS["min_patch_ha"] / px_ha))
    tf = transform_from_coords(ds.x.values, ds.y.values)
    tr = Transformer.from_crs(C.CRS, "EPSG:4326", always_xy=True)

    def to_ll(c):
        lon, lat = tr.transform(c[:, 0], c[:, 1])
        return np.column_stack([lon, lat])
    hv_db, hh_db = to_db(ds.hv.values), to_db(ds.hh.values)
    water = ds.water.values.astype(bool)
    from scipy.ndimage import binary_dilation
    near_water = binary_dilation(water, iterations=2)
    pv = list(ds.processing_version.values)

    feats, series = [], {}
    keep = np.zeros_like(lab)
    k = 0
    for i in range(1, n + 1):
        m = lab == i
        if m.sum() < min_px:
            continue
        k += 1
        keep[m] = k
        t0 = int(np.bincount(first[m][first[m] >= 0]).argmax())
        post = slice(t0, None)
        flags = []
        hh_change = float(np.nanmean(hh_db[post][:, m]) - np.nanmean(hh_db[:t0][:, m]))
        if hh_change > 1.0:
            flags.append("hh_rise")
        if (m & near_water).any():
            flags.append("water")
        if t0 > 0 and pv[t0] != pv[t0 - 1]:
            flags.append("calibration")
        if t0 == len(times) - 1:
            flags.append("rain")
        pid = f"P{k:04d}"
        series[pid] = {"hv_db": [round(float(v), 2) for v in np.nanmean(hv_db[:, m], axis=1)],
                       "hh_db": [round(float(v), 2) for v in np.nanmean(hh_db[:, m], axis=1)]}
        feats.append({"pid": pid, "t0": t0, "area_ha": round(float(m.sum() * px_ha), 2),
                      "n_dates": int(np.median(ch.n_changed.values[m])),
                      "drop": round(float(np.nanmean(lr[post][:, m])), 2),
                      "hh_change": round(hh_change, 2), "flags": flags})

    geoms = {}
    for geom, val in shapes(keep.astype("int32"), mask=keep > 0, transform=tf):
        geoms.setdefault(int(val), []).append(shape(geom))
    fc = []
    for f in feats:
        k = int(f["pid"][1:])
        g = shapely.transform(unary_union(geoms[k]).simplify(1.0), to_ll)
        fc.append({"type": "Feature", "geometry": mapping(g), "properties": {
            "patch_id": f["pid"], "area_ha": f["area_ha"],
            "first_change_date": times[f["t0"]], "prev_acq_date": times[max(f["t0"] - 1, 0)],
            "n_dates_changed": f["n_dates"], "mean_drop_hv_db": f["drop"],
            "hh_change_db": f["hh_change"], "flags": f["flags"]}})

    stable = (~water) & (keep == 0)
    ts = {"dates": times, "patches": series,
          "reference": {"hv_db": [round(float(v), 2) for v in np.nanmedian(hv_db[:, stable], axis=1)],
                        "hh_db": [round(float(v), 2) for v in np.nanmedian(hh_db[:, stable], axis=1)]}}
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    (C.PROCESSED / "patches.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": fc}))
    (C.PROCESSED / "timeseries.json").write_text(json.dumps(ts))
    print(f"[S2] {len(fc)} patches >= {C.PARAMS['min_patch_ha']} ha")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--method", choices=["omnibus", "logratio"], default="omnibus")
    ap.add_argument("--threshold", default=C.PARAMS["logratio_threshold_db"],
                    help="dB, or 'auto' for the 1st percentile of reference-date ratios")
    ap.add_argument("--alpha", type=float, default=C.PARAMS["omnibus_alpha"])
    ap.add_argument("--smooth", type=int, default=3, help="boxcar size in pixels (1 = off)")
    a = ap.parse_args()
    run(a.method, a.threshold if a.threshold == "auto" else float(a.threshold), a.alpha, a.smooth)


if __name__ == "__main__":
    main()

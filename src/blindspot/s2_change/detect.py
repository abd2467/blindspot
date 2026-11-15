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
    return np.divide(num, den, out=np.full_like(num, np.nan), where=den > 1e-8)


def reference_mean(a, indices):
    """Mean reference power, retaining NaN where no observation is available."""
    ref = a[indices]
    count = np.isfinite(ref).sum(axis=0)
    return np.divide(np.nansum(ref, axis=0), count,
                     out=np.full(a.shape[1:], np.nan), where=count > 0)


def reference_indices(times):
    """Find configured reference dates, rejecting unusable input timelines."""
    idx = [i for i, t in enumerate(times) if t in C.REFERENCE_DATES]
    if len(idx) < 2:
        raise ValueError("At least two configured reference dates are needed")
    if times != sorted(set(times)):
        raise ValueError("Acquisition dates must be unique and chronological")
    return idx


def normalised_logratio(hv: np.ndarray, times: list[str], water: np.ndarray, smooth: int = 3,
                        stable_mask=None) -> np.ndarray:
    """HV log-ratio (dB) against a reference mean after per-date normalisation.

    Scale dates before forming the reference to cancel scene-wide shifts from
    rain, moisture and calibration. Use a reviewed stable polygon if supplied.
    """
    ref_idx = reference_indices(times)
    hv_s = normalise_scene(boxcar(hv, smooth), times, water, stable_mask)
    ref = reference_mean(hv_s, ref_idx)
    lr = to_db(hv_s / ref[None])
    land = water == 0
    lr[:, ~land] = np.nan
    return lr


def normalise_scene(a: np.ndarray, times: list[str], water: np.ndarray, stable_mask=None) -> np.ndarray:
    """Scale each date so its median ratio to the reference mean over land is 1."""
    ref_idx = reference_indices(times)
    ref = reference_mean(a, ref_idx)
    land = (water == 0) & np.all(np.isfinite(a) & (a > 0), axis=0)
    if stable_mask is not None:
        land &= stable_mask
    if not land.any():
        raise ValueError("Normalisation needs valid non-water pixels in the stable area")
    out = a.copy()
    for t in range(a.shape[0]):
        with np.errstate(invalid="ignore", divide="ignore"):
            out[t] /= np.nanmedian((a[t] / ref)[land])
    return out


def estimate_enl(a: np.ndarray, times: list[str], water: np.ndarray, stable_mask=None) -> float:
    """Pool reference temporal moments; correct the mean-square finite-sample bias.

    Pooling avoids taking a median of noisy ratios from only four observations.
    """
    ref_idx = reference_indices(times)
    valid = (water == 0) & np.all(np.isfinite(a) & (a > 0), axis=0)
    if stable_mask is not None:
        valid &= stable_mask
    r = a[ref_idx][:, valid]
    variance = np.sum(np.var(r, axis=0, ddof=1))
    enl = np.sum(np.mean(r, axis=0) ** 2) / variance - 1 / len(ref_idx) if variance > 0 else np.nan
    if not np.isfinite(enl) or enl <= 0:
        raise ValueError("Cannot estimate effective looks from reference variability")
    return float(enl)


def filter_small_patches(first):
    """Apply the configured minimum area to 8-connected change components."""
    from scipy.ndimage import label

    labels, _ = label(first >= 0, structure=np.ones((3, 3)))
    sizes = np.bincount(labels.ravel())
    keep = sizes * pixel_area_ha() >= C.PARAMS["min_patch_ha"]
    keep[0] = False
    return np.where(keep[labels], first, -1).astype("int16")


def load_stable_mask(ds, path=None):
    """Rasterise a reviewed WGS84 polygon; use scene land if none is supplied."""
    from pathlib import Path
    import geopandas as gpd
    from rasterio.features import geometry_mask

    candidate = Path(path) if path is not None else C.PROCESSED / "stable_area.geojson"
    if path is None and not candidate.exists():
        return None
    polygons = gpd.read_file(candidate)
    if polygons.empty or not polygons.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("Stable area must contain polygons")
    if polygons.crs is None:
        raise ValueError("Stable area must declare its coordinate system")
    return geometry_mask(polygons.to_crs(C.CRS).geometry, out_shape=ds.water.shape,
                         transform=transform_from_coords(ds.x.values, ds.y.values), invert=True)


def persistent(mask_t: np.ndarray, n: int) -> np.ndarray:
    """True at date t where mask holds on dates t..t+n-1."""
    out = mask_t.copy()
    for s in range(1, n):
        shifted = np.zeros_like(mask_t)
        shifted[:-s] = mask_t[s:]
        out &= shifted
    return out


def reference_drift(lr, ref_idx, limit=None):
    """True where normalised HV fell by `limit` dB or more within the reference dates."""
    limit = C.PARAMS["reference_drift_db"] if limit is None else limit
    if len(ref_idx) < 4:
        return np.zeros(lr.shape[1:], bool)
    half = len(ref_idx) // 2
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            early = np.nanmean(lr[ref_idx[:half]], axis=0)
            late = np.nanmean(lr[ref_idx[half:]], axis=0)
    return np.nan_to_num(late - early, nan=0.0) <= limit


def detect_arrays(hh, hv, water, times, enl, method="omnibus",
                  threshold=C.PARAMS["logratio_threshold_db"], alpha=C.PARAMS["omnibus_alpha"], smooth=3,
                  stable_mask=None):
    """Core detector on in-memory arrays. Returns (first_change_index, p_value, logratio_db, description).

    Kept separate from file I/O so the synthetic burn test can call it directly.
    """
    if method not in ("omnibus", "logratio") or not 0 < alpha < 1:
        raise ValueError("Unknown method or alpha outside (0, 1)")
    if smooth < 1 or smooth % 2 != 1:
        raise ValueError("Smoothing size must be a positive odd integer")
    if hh.shape != hv.shape or hh.shape != (len(times), *water.shape):
        raise ValueError("HH, HV, water and dates have incompatible shapes")
    ref_idx = reference_indices(times)
    valid = (water == 0) & np.all(np.isfinite(hh) & np.isfinite(hv) & (hh > 0) & (hv > 0), axis=0)
    hh = np.where(valid[None], hh, np.nan)
    hv = np.where(valid[None], hv, np.nan)
    lr = normalised_logratio(hv, times, water, smooth, stable_mask)
    ncons = C.PARAMS["min_consecutive_dates"]
    eligible = persistent(lr <= -1.0, ncons) & valid[None]
    eligible[:max(ref_idx) + 1] = False
    # Reference check promised in config.REFERENCE_DATES: pixels whose HV was already
    # falling across the reference dates (late half vs early half) are not eligible,
    # so seasonal drying that starts in July is not read as later change.
    eligible &= ~reference_drift(lr, ref_idx)[None]
    if method == "logratio":
        if threshold == "auto":
            # noise tail: 1st percentile of the reference-date ratios
            threshold = float(np.nanpercentile(lr[ref_idx], 1))
        if not np.isfinite(float(threshold)) or float(threshold) >= 0:
            raise ValueError("Log-ratio threshold must be finite and negative")
        below = lr < float(threshold)
        ok = persistent(below, ncons) & eligible
        first = np.where(ok.any(0), ok.argmax(0), -1).astype("int16")
        pval = np.full(first.shape, np.nan, "float32")
        desc = f"logratio threshold {float(threshold):.2f} dB, {ncons} consecutive dates"
    else:
        # Radiometric normalisation (uncertainty layer 2): divide each date by its scene-median
        # ratio to the reference, per band, so rain, soil moisture and calibration jumps that
        # shift the whole scene are not read as change by the omnibus test.
        hh_s = normalise_scene(boxcar(hh, smooth), times, water, stable_mask)
        hv_s = normalise_scene(boxcar(hv, smooth), times, water, stable_mask)
        # Effective looks after smoothing, measured from the data instead of assumed:
        # over reference dates (no change expected), pool temporal mean^2 and variance.
        enl_eff = estimate_enl(hv_s, times, water, stable_mask)
        idx, pval, _ = first_change(hh_s, hv_s, enl_eff, alpha, eligible=eligible)
        first = idx
        desc = f"sequential omnibus alpha {alpha}, ENL_eff {enl_eff:.1f}, HV persists below -1 dB for {ncons} dates"
    first[~valid] = -1
    first = filter_small_patches(first)
    pval[first < 0] = np.nan
    desc += f", boxcar {smooth}, minimum patch {C.PARAMS['min_patch_ha']} ha, "
    desc += "stable polygon normalisation" if stable_mask is not None else "scene land normalisation"
    return first, pval, lr, desc


def run(method: str = "omnibus", threshold: float | str = C.PARAMS["logratio_threshold_db"],
        alpha: float = C.PARAMS["omnibus_alpha"], smooth: int = 3, stable_area=None):
    import xarray as xr

    ds = xr.open_dataset(C.INTERIM / "stack.nc")
    times = [str(t)[:10] for t in ds.time.values]
    hh, hv = ds.hh.values.astype("float64"), ds.hv.values.astype("float64")
    water = ds.water.values
    stable_mask = load_stable_mask(ds, stable_area)
    first, pval, lr, desc = detect_arrays(hh, hv, water, times, ds.attrs["enl"], method, threshold, alpha, smooth, stable_mask)
    changed = first >= 0
    n_changed = np.where(changed, np.sum(lr <= -1.0, axis=0), 0).astype("int16")
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
    ds.close()
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
    invalid = ~np.all(np.isfinite(ds.hh.values) & np.isfinite(ds.hv.values)
                      & (ds.hh.values > 0) & (ds.hv.values > 0), axis=0)
    near_edge = binary_dilation(invalid, structure=np.ones((3, 3)))
    near_edge[[0, -1], :] = True
    near_edge[:, [0, -1]] = True
    # Swath edge: speckle and dark-edge artefacts rise within a few km of the no-data gap.
    gap = np.all(~(np.isfinite(ds.hv.values) & (ds.hv.values > 0)), axis=0)
    if gap.any():
        from scipy.ndimage import distance_transform_edt
        res_km = abs(float(ds.x.values[1] - ds.x.values[0])) / 1000
        near_edge |= distance_transform_edt(~gap) * res_km <= C.PARAMS["edge_buffer_km"]
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
        if (m & near_edge).any():
            flags.append("edge")
        hh_change = float(np.nanmean(hh_db[post][:, m]) - np.nanmean(hh_db[:t0][:, m]))
        if hh_change > 1.0:
            flags.append("hh_rise")
        if (m & near_water).any():
            flags.append("water")
        if t0 > 0 and pv[t0] != pv[t0 - 1]:
            flags.append("calibration")
        if times[t0] >= C.ACQ_DATES[-2]:
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

    stable = (~water) & (~changed) & (~invalid)
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
    ap.add_argument("--stable-area", help="reviewed stable forest GeoJSON; defaults to processed/stable_area.geojson if present")
    a = ap.parse_args()
    run(a.method, a.threshold if a.threshold == "auto" else float(a.threshold), a.alpha, a.smooth, a.stable_area)


if __name__ == "__main__":
    main()

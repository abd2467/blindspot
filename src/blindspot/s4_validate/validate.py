"""S4: validation, evidence review and the error-adjusted area estimate.

    python -m blindspot.s4_validate.validate sample   # draw the stratified reference sample to label
    python -m blindspot.s4_validate.validate review   # create/refresh review.csv (confidence tiers)
    python -m blindspot.s4_validate.validate radd     # agreement with RADD (needs data/raw/radd_alerts.tif)
    python -m blindspot.s4_validate.validate stats    # Olofsson area + CI, write validation_stats.json

The labelling itself is human work: open data/processed/reference_sample.csv,
look at each point in Sentinel-2 / HLS and RADD, and fill the `label` column with
one of: burn, clearing, flood, no_change, unclear. See docs/workstreams/WS4_validation.md.
"""
from __future__ import annotations

import csv
import json
import sys

import numpy as np

from .. import config as C
from ..grid import pixel_area_ha

STRATA = ("change_hotspot", "change_no_hotspot", "no_change")
LABELS = ("burn", "clearing", "flood", "no_change", "unclear")
SAMPLE_PER_STRATUM = {"change_hotspot": 15, "change_no_hotspot": 20, "no_change": 15}


def _strata_raster():
    """Per-pixel stratum (0,1,2; -1 = water) using patches and the cross-check."""
    import geopandas as gpd
    import xarray as xr
    from rasterio.features import rasterize

    from ..grid import transform_from_coords

    ch = xr.open_dataset(C.INTERIM / "change.nc")
    st = xr.open_dataset(C.INTERIM / "stack.nc")
    patches = gpd.read_file(C.PROCESSED / "patches.geojson").to_crs(C.CRS)
    status = {r["patch_id"]: r["hotspot_status"] for r in csv.DictReader(open(C.PROCESSED / "crosscheck.csv"))}
    tf = transform_from_coords(ch.x.values, ch.y.values)
    code = {"recorded": 1, "none": 2, "insufficient_data": 3}
    shapes = [(g, code[status.get(pid, "none")]) for g, pid in zip(patches.geometry, patches.patch_id)]
    lab = rasterize(shapes, out_shape=ch.changed.shape, transform=tf, fill=0, dtype="uint8") if shapes \
        else np.zeros(ch.changed.shape, "uint8")
    strata = np.full(lab.shape, 2, "int8")      # no_change
    strata[lab == 1] = 0                        # change_hotspot
    strata[lab == 2] = 1                        # change_no_hotspot
    strata[(lab == 3) | (st.water.values == 1)] = -1  # excluded
    return strata, ch.x.values, ch.y.values


def sample(seed: int = 42):
    from pyproj import Transformer

    strata, x, y = _strata_raster()
    rng = np.random.default_rng(seed)
    to_ll = Transformer.from_crs(C.CRS, "EPSG:4326", always_xy=True)
    rows = []
    for k, name in enumerate(STRATA):
        rr, cc = np.nonzero(strata == k)
        n = min(SAMPLE_PER_STRATUM[name], rr.size)
        pick = rng.choice(rr.size, n, replace=False) if n else []
        for j, i in enumerate(pick):
            lon, lat = to_ll.transform(x[cc[i]], y[rr[i]])
            rows.append({"point_id": f"{name[:2].upper()}{j:03d}", "stratum": name,
                         "lon": round(lon, 6), "lat": round(lat, 6), "label": "", "labeller": "", "notes": ""})
    counts = {name: int((strata == k).sum()) for k, name in enumerate(STRATA)}
    out = C.PROCESSED / "reference_sample.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (C.PROCESSED / "strata_pixel_counts.json").write_text(json.dumps(counts, indent=1))
    print(f"[S4] {len(rows)} points -> {out}. Label them by hand (burn/clearing/flood/no_change/unclear).")


def olofsson(sample_rows, pixel_counts, target=("burn", "clearing")):
    """Stratified estimator of the area of real disturbance (Olofsson et al. 2014).

    Returns km2 with a 95% CI. 'unclear' labels are dropped from their stratum.
    """
    total_px = sum(pixel_counts.values())
    p_hat, var = 0.0, 0.0
    used = {}
    for name in STRATA:
        labs = [r["label"] for r in sample_rows if r["stratum"] == name and r["label"] in LABELS and r["label"] != "unclear"]
        n = len(labs)
        used[name] = n
        if n == 0:
            continue
        W = pixel_counts[name] / total_px
        p = sum(lab in target for lab in labs) / n
        p_hat += W * p
        if n > 1:
            var += W ** 2 * p * (1 - p) / (n - 1)
    area_total_km2 = total_px * pixel_area_ha() / 100
    se = np.sqrt(var) * area_total_km2
    est = p_hat * area_total_km2
    return {"km2": round(est, 3), "ci95_low": round(max(est - 1.96 * se, 0), 3),
            "ci95_high": round(est + 1.96 * se, 3), "n_used": used, "target_labels": list(target)}


def review():
    """Make review.csv with a rule-based confidence tier. Humans then edit `interpretation`."""
    path = C.PROCESSED / "review.csv"
    old = {r["patch_id"]: r for r in csv.DictReader(open(path))} if path.exists() else {}
    feats = json.loads((C.PROCESSED / "patches.geojson").read_text())["features"]
    radd = json.loads((C.PROCESSED / "radd_by_patch.json").read_text()) if (C.PROCESSED / "radd_by_patch.json").exists() else {}
    rows = []
    for ft in feats:
        p = ft["properties"]
        pid = p["patch_id"]
        agree = radd.get(pid)
        strong = p["n_dates_changed"] >= 3 and p["mean_drop_hv_db"] <= -3
        if strong and not p["flags"] and agree is not False:
            tier = "high"
        elif p["flags"] or p["n_dates_changed"] < 2:
            tier = "low"
        else:
            tier = "medium"
        keep = old.get(pid, {})
        rows.append({"patch_id": pid, "confidence_tier": tier,
                     "interpretation": keep.get("interpretation") or ("not_assessable" if "water" in p["flags"] else "unreviewed"),
                     "radd_agree": "" if agree is None else str(agree).lower(),
                     "notes": keep.get("notes", ""), "evidence_urls": keep.get("evidence_urls", "")})
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[S4] review.csv: {len(rows)} patches. Edit 'interpretation' for the patches you review.")


def radd():
    """Share of each patch covered by a RADD alert dated inside its window (data/raw/radd_alerts.tif).

    The GeoTIFF must be on the analysis grid with the alert date as days since 2014-12-31
    (that is how the RADD 'Date' band is encoded; check the dataset page). Export it from
    Earth Engine with the snippet in docs/workstreams/WS4_validation.md.
    """
    from datetime import date

    import rasterio
    from rasterio.features import rasterize

    with rasterio.open(C.RAW / "radd_alerts.tif") as src:
        alert_day = src.read(1)
        tf = src.transform
    import geopandas as gpd

    patches = gpd.read_file(C.PROCESSED / "patches.geojson").to_crs(C.CRS)
    epoch = date(2014, 12, 31).toordinal()
    out = {}
    for g, pid, d0, d1 in zip(patches.geometry, patches.patch_id, patches.prev_acq_date, patches.first_change_date):
        m = rasterize([(g, 1)], out_shape=alert_day.shape, transform=tf, fill=0, dtype="uint8").astype(bool)
        lo = date.fromisoformat(str(d0)[:10]).toordinal() - epoch - 30
        hi = date.fromisoformat(str(d1)[:10]).toordinal() - epoch + 12
        hit = (alert_day[m] >= lo) & (alert_day[m] <= hi)
        out[pid] = bool(hit.mean() >= 0.3) if m.any() else None
    (C.PROCESSED / "radd_by_patch.json").write_text(json.dumps(out, indent=1))
    vals = [v for v in out.values() if v is not None]
    print(f"[S4] RADD agrees on {np.mean(vals):.0%} of {len(vals)} patches")


def stats():
    out = {"radd_agreement": None, "sample": None, "area_estimate": None, "synthetic": None}
    rp = C.PROCESSED / "radd_by_patch.json"
    if rp.exists():
        vals = [v for v in json.loads(rp.read_text()).values() if v is not None]
        out["radd_agreement"] = {"share": round(float(np.mean(vals)), 3) if vals else None, "n_patches": len(vals)}
    sp = C.PROCESSED / "reference_sample.csv"
    if sp.exists():
        rows = list(csv.DictReader(open(sp)))
        labelled = [r for r in rows if r["label"]]
        out["sample"] = {"n": len(rows), "n_labelled": len(labelled)}
        if labelled:
            counts = json.loads((C.PROCESSED / "strata_pixel_counts.json").read_text())
            out["area_estimate"] = olofsson(labelled, counts)
    sc = C.PROCESSED / "synthetic_curve.json"
    if sc.exists():
        out["synthetic"] = json.loads(sc.read_text())
    (C.PROCESSED / "validation_stats.json").write_text(json.dumps(out, indent=1))
    print("[S4] validation_stats.json written:", {k: (v is not None) for k, v in out.items()})


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    {"sample": sample, "review": review, "radd": radd, "stats": stats}[cmd]()

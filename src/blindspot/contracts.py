"""Checks that every hand-off file matches docs/CONTRACTS.md.

Each workstream runs the check for the files it produces before opening a PR:

    python -m blindspot.contracts stack data/interim/stack.nc
    python -m blindspot.contracts all          # checks every file that exists

A check returns a list of problems. An empty list means the file is valid.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from . import config as C

ISO_DATE_LEN = 10


def _is_date(s) -> bool:
    return isinstance(s, str) and len(s) == ISO_DATE_LEN and s[4] == "-" and s[7] == "-"


# ---------------------------------------------------------------------------
# Rasters (NetCDF, written with xarray)
# ---------------------------------------------------------------------------
def check_stack(path) -> list[str]:
    """WS1 -> WS2, WS4, WS5: data/interim/stack.nc"""
    import numpy as np
    import xarray as xr

    errs = []
    ds = xr.open_dataset(path)
    for v in ("hh", "hv", "water"):
        if v not in ds:
            errs.append(f"missing variable '{v}'")
    if errs:
        return errs
    if ds["hh"].dims != ("time", "y", "x") or ds["hv"].dims != ("time", "y", "x"):
        errs.append("hh and hv must have dims (time, y, x)")
    if ds["water"].dims != ("y", "x"):
        errs.append("water must have dims (y, x)")
    if ds.attrs.get("crs") != C.CRS:
        errs.append(f"attrs['crs'] must be {C.CRS}")
    if "enl" not in ds.attrs:
        errs.append("attrs['enl'] (equivalent number of looks) is required")
    dx = float(ds.x[1] - ds.x[0])
    dy = float(ds.y[1] - ds.y[0])
    if abs(dx - C.RES_M) > 1e-6 or abs(dy + C.RES_M) > 1e-6:
        errs.append(f"pixel spacing must be +{C.RES_M} in x and -{C.RES_M} in y (north-up), got {dx}, {dy}")
    if "processing_version" not in ds.coords:
        errs.append("coordinate 'processing_version' along time is required")
    hv = ds["hv"].values
    finite = hv[np.isfinite(hv)]
    if finite.size and (finite.min() < 0 or np.median(finite) > 1):
        errs.append("hh/hv must be LINEAR power (sigma0 or gamma0), not dB")
    if not ds.attrs.get("fixture", False):
        if tuple(ds["hv"].shape[1:]) != C.GRID_SHAPE:
            errs.append(f"real data must be on the full grid {C.GRID_SHAPE}")
        dates = [str(t)[:10] for t in ds.time.values]
        missing = sorted(set(C.ACQ_DATES) - set(dates))
        if missing:
            errs.append(f"dates missing from stack (fine if documented in attrs['notes']): {missing}")
    return errs


def check_change(path) -> list[str]:
    """WS2 -> WS3, WS4, WS5: data/interim/change.nc"""
    import xarray as xr

    errs = []
    ds = xr.open_dataset(path)
    for v in ("changed", "first_change", "n_changed", "min_logratio_db"):
        if v not in ds:
            errs.append(f"missing variable '{v}'")
        elif ds[v].dims != ("y", "x"):
            errs.append(f"{v} must have dims (y, x)")
    if "method" not in ds.attrs:
        errs.append("attrs['method'] must say which test produced the mask")
    return errs


# ---------------------------------------------------------------------------
# Vectors and tables
# ---------------------------------------------------------------------------
def _features(path):
    with open(path) as f:
        gj = json.load(f)
    if gj.get("type") != "FeatureCollection":
        raise ValueError("not a GeoJSON FeatureCollection")
    return gj["features"]


def check_patches(path) -> list[str]:
    """WS2 -> WS3, WS4, S5: data/processed/patches.geojson (EPSG:4326)"""
    errs = []
    req = {"patch_id", "area_ha", "first_change_date", "prev_acq_date",
           "n_dates_changed", "mean_drop_hv_db", "hh_change_db", "flags"}
    ids = set()
    for i, ft in enumerate(_features(path)):
        p = ft.get("properties", {})
        miss = req - set(p)
        if miss:
            errs.append(f"feature {i}: missing {sorted(miss)}")
            continue
        if p["patch_id"] in ids:
            errs.append(f"duplicate patch_id {p['patch_id']}")
        ids.add(p["patch_id"])
        if not (_is_date(p["first_change_date"]) and _is_date(p["prev_acq_date"])):
            errs.append(f"{p['patch_id']}: dates must be YYYY-MM-DD")
        if not isinstance(p["flags"], list) or set(p["flags"]) - set(C.PATCH_FLAGS):
            errs.append(f"{p['patch_id']}: flags must be a list drawn from {C.PATCH_FLAGS}")
        if ft["geometry"]["type"] not in ("Polygon", "MultiPolygon"):
            errs.append(f"{p['patch_id']}: geometry must be (Multi)Polygon")
        lon, lat = _first_coord(ft["geometry"])
        if not (100 < lon < 125 and -10 < lat < 10):
            errs.append(f"{p['patch_id']}: coordinates must be lon/lat (EPSG:4326)")
    return errs


def _first_coord(geom):
    c = geom["coordinates"]
    while isinstance(c[0], list):
        c = c[0]
    return c[0], c[1]


def check_timeseries(path) -> list[str]:
    """WS2 -> S5, WS5: data/processed/timeseries.json"""
    errs = []
    with open(path) as f:
        ts = json.load(f)
    for k in ("dates", "patches", "reference"):
        if k not in ts:
            errs.append(f"missing key '{k}'")
    if errs:
        return errs
    n = len(ts["dates"])
    for pid, s in list(ts["patches"].items())[:50]:
        for band in ("hv_db", "hh_db"):
            if len(s.get(band, [])) != n:
                errs.append(f"{pid}: {band} must have one value per date ({n})")
    return errs


def check_hotspots(path) -> list[str]:
    """WS3 -> S5: data/processed/hotspots.geojson (EPSG:4326 points)"""
    errs = []
    req = {"sensor", "satellite", "acq_date", "acq_time", "confidence", "frp", "source"}
    for i, ft in enumerate(_features(path)):
        p = ft.get("properties", {})
        miss = req - set(p)
        if miss:
            errs.append(f"feature {i}: missing {sorted(miss)}")
            break
        if p["sensor"] not in ("VIIRS", "MODIS"):
            errs.append(f"feature {i}: sensor must be VIIRS or MODIS")
            break
        if ft["geometry"]["type"] != "Point":
            errs.append(f"feature {i}: geometry must be Point")
            break
    return errs


def _rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def check_crosscheck(path) -> list[str]:
    """WS3 -> S5, WS4: data/processed/crosscheck.csv"""
    errs = []
    rows = _rows(path)
    req = {"patch_id", "hotspot_status", "n_hotspots", "nearest_hotspot_km", "window_start", "window_end"}
    if rows and req - set(rows[0]):
        return [f"missing columns {sorted(req - set(rows[0]))}"]
    for r in rows:
        if r["hotspot_status"] not in C.HOTSPOT_STATUS:
            errs.append(f"{r['patch_id']}: hotspot_status must be one of {C.HOTSPOT_STATUS}")
    return errs


def check_crosscheck_stats(path) -> list[str]:
    """WS3 -> S5: data/processed/crosscheck_stats.json"""
    with open(path) as f:
        s = json.load(f)
    req = {"total_change_km2", "no_hotspot_km2", "no_hotspot_share", "mc", "params", "by_date"}
    errs = [f"missing key '{k}'" for k in sorted(req - set(s))]
    if "mc" in s and not {"p05", "p50", "p95", "runs"} <= set(s["mc"]):
        errs.append("mc must contain p05, p50, p95, runs")
    return errs


def check_review(path) -> list[str]:
    """WS4 -> S5: data/processed/review.csv"""
    errs = []
    rows = _rows(path)
    req = {"patch_id", "confidence_tier", "interpretation", "radd_agree", "notes"}
    if rows and req - set(rows[0]):
        return [f"missing columns {sorted(req - set(rows[0]))}"]
    for r in rows:
        if r["confidence_tier"] not in C.CONFIDENCE_TIER:
            errs.append(f"{r['patch_id']}: confidence_tier must be one of {C.CONFIDENCE_TIER}")
        if r["interpretation"] not in C.INTERPRETATION:
            errs.append(f"{r['patch_id']}: interpretation must be one of {C.INTERPRETATION}")
    return errs


def check_validation_stats(path) -> list[str]:
    """WS4 -> S5: data/processed/validation_stats.json"""
    with open(path) as f:
        s = json.load(f)
    req = {"radd_agreement", "sample", "area_estimate", "synthetic"}
    errs = [f"missing key '{k}'" for k in sorted(req - set(s))]
    if "area_estimate" in s and s["area_estimate"] and not {"km2", "ci95_low", "ci95_high"} <= set(s["area_estimate"]):
        errs.append("area_estimate must contain km2, ci95_low, ci95_high (or be null)")
    return errs


def check_psi(path) -> list[str]:
    """WS6 -> S5: data/processed/psi_daily.csv"""
    rows = _rows(path)
    if not rows:
        return ["empty file"]
    req = {"date", "psi_24h_max"}
    if req - set(rows[0]):
        return [f"missing columns {sorted(req - set(rows[0]))}"]
    return [f"bad date {r['date']}" for r in rows if not _is_date(r["date"])][:5]


def check_rain(path) -> list[str]:
    """WS4 -> S5: data/processed/rain_daily.csv"""
    rows = _rows(path)
    if not rows:
        return ["empty file"]
    req = {"date", "precip_mm"}
    return [f"missing columns {sorted(req - set(rows[0]))}"] if req - set(rows[0]) else []


def check_events(path) -> list[str]:
    """WS6 -> S5: data/processed/eonet_events.geojson"""
    errs = []
    for i, ft in enumerate(_features(path)):
        p = ft.get("properties", {})
        if not {"id", "title", "date"} <= set(p):
            errs.append(f"feature {i}: needs id, title, date")
            break
    return errs


CHECKS = {
    "stack": (check_stack, C.INTERIM / "stack.nc"),
    "change": (check_change, C.INTERIM / "change.nc"),
    "patches": (check_patches, C.PROCESSED / "patches.geojson"),
    "timeseries": (check_timeseries, C.PROCESSED / "timeseries.json"),
    "hotspots": (check_hotspots, C.PROCESSED / "hotspots.geojson"),
    "crosscheck": (check_crosscheck, C.PROCESSED / "crosscheck.csv"),
    "crosscheck_stats": (check_crosscheck_stats, C.PROCESSED / "crosscheck_stats.json"),
    "review": (check_review, C.PROCESSED / "review.csv"),
    "validation_stats": (check_validation_stats, C.PROCESSED / "validation_stats.json"),
    "psi": (check_psi, C.PROCESSED / "psi_daily.csv"),
    "rain": (check_rain, C.PROCESSED / "rain_daily.csv"),
    "events": (check_events, C.PROCESSED / "eonet_events.geojson"),
}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        print("names:", ", ".join(CHECKS), "or 'all'")
        return 0
    if argv[0] == "all":
        targets = [(n, fn, p) for n, (fn, p) in CHECKS.items() if Path(p).exists()]
    else:
        fn, default = CHECKS[argv[0]]
        targets = [(argv[0], fn, Path(argv[1]) if len(argv) > 1 else default)]
    bad = 0
    for name, fn, path in targets:
        errs = fn(path)
        status = "OK " if not errs else "FAIL"
        print(f"[{status}] {name:17s} {path}")
        for e in errs:
            print(f"        - {e}")
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

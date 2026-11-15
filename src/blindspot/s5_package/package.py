"""S5: merge every workstream's outputs into the small files the web app reads (web/data/).

    python -m blindspot.s5_package.package

Missing inputs are skipped with a warning, so the app always gets a valid manifest.
Only this script writes to web/data/. The integration lead owns it.
"""
from __future__ import annotations

import csv
import json
import re
import shutil
from datetime import datetime, timezone

import numpy as np

from .. import config as C

HV_DB_RANGE = (-20.0, -5.0)  # display stretch for the radar overlays


def _warn(msg):
    print(f"[S5] skip: {msg}")


def _to_wgs84(arr, src_tf, resampling="bilinear"):
    """Reproject one grid array from the analysis CRS to EPSG:4326. Returns (array, transform)."""
    from rasterio.crs import CRS
    from rasterio.warp import Resampling, calculate_default_transform, reproject

    ny, nx = arr.shape
    src_crs, dst_crs = CRS.from_string(C.CRS), CRS.from_epsg(4326)
    xmin, ymax = src_tf.c, src_tf.f
    bounds = (xmin, ymax - ny * abs(src_tf.e), xmin + nx * src_tf.a, ymax)
    dst_tf, w, h = calculate_default_transform(src_crs, dst_crs, nx, ny, *bounds)
    dst = np.full((h, w), np.nan, "float32")
    reproject(arr.astype("float32"), dst, src_transform=src_tf, src_crs=src_crs, dst_transform=dst_tf,
              dst_crs=dst_crs, resampling=getattr(Resampling, resampling), src_nodata=np.nan, dst_nodata=np.nan)
    return dst, dst_tf


def _leaflet_bounds(dst_tf, shape):
    h, w = shape
    west, north = dst_tf.c, dst_tf.f
    east, south = west + w * dst_tf.a, north + h * dst_tf.e
    return [[south, west], [north, east]]


def _overlays(manifest):
    import xarray as xr
    from PIL import Image

    from ..grid import to_db, transform_from_coords

    path = C.INTERIM / "stack.nc"
    if not path.exists():
        return _warn("stack.nc")
    ds = xr.open_dataset(path)
    src_tf = transform_from_coords(ds.x.values, ds.y.values)
    out_dir = C.WEB_DATA / "overlays"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("hv_*.png"):
        old.unlink()
    lo, hi = HV_DB_RANGE
    manifest["overlays"] = {}
    for i, t in enumerate(ds.time.values):
        d = str(t)[:10]
        dst, dst_tf = _to_wgs84(to_db(ds.hv.values[i]), src_tf)
        h, w = dst.shape
        g = np.clip((dst - lo) / (hi - lo), 0, 1)
        rgba = np.zeros((h, w, 4), "uint8")
        rgba[..., :3] = (np.nan_to_num(g) * 255).astype("uint8")[..., None]
        rgba[..., 3] = np.where(np.isfinite(dst), 255, 0)
        name = f"overlays/hv_{d}.png"
        Image.fromarray(rgba, "RGBA").save(C.WEB_DATA / name, optimize=True)
        manifest["overlays"][d] = name
    manifest["bounds"] = _leaflet_bounds(dst_tf, (h, w))  # Leaflet order
    manifest["dates"] = [str(t)[:10] for t in ds.time.values]
    manifest["processing_version"] = [str(v) for v in ds.processing_version.values]
    manifest["display_db_range"] = list(HV_DB_RANGE)


def _peat(manifest):
    """Optional: WS4's peat_mask.tif as a translucent overlay (1 = peat-dominated, 2 = peat in mosaic)."""
    path = C.PROCESSED / "peat_mask.tif"
    if not path.exists():
        return None
    import rasterio
    from PIL import Image

    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
        tf = src.transform
    dst, dst_tf = _to_wgs84(arr, tf, "nearest")
    rgba = np.zeros(dst.shape + (4,), "uint8")
    rgba[dst == 1] = (124, 92, 52, 150)
    rgba[dst == 2] = (124, 92, 52, 80)
    (C.WEB_DATA / "overlays").mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(C.WEB_DATA / "overlays" / "peat.png", optimize=True)
    manifest["peat"] = {"url": "overlays/peat.png", "bounds": _leaflet_bounds(dst_tf, dst.shape)}


def _rows(path):
    return {r["patch_id"]: r for r in csv.DictReader(open(path))} if path.exists() else {}


def _patches():
    p = C.PROCESSED / "patches.geojson"
    if not p.exists():
        return _warn("patches.geojson")
    gj = json.loads(p.read_text())
    cc = _rows(C.PROCESSED / "crosscheck.csv")
    rv = _rows(C.PROCESSED / "review.csv")
    for ft in gj["features"]:
        pr = ft["properties"]
        c, r = cc.get(pr["patch_id"], {}), rv.get(pr["patch_id"], {})
        pr["hotspot_status"] = c.get("hotspot_status", "unknown")
        pr["n_hotspots"] = int(c.get("n_hotspots") or 0)
        pr["nearest_hotspot_km"] = float(c["nearest_hotspot_km"]) if c.get("nearest_hotspot_km") else None
        pr["window_start"] = c.get("window_start") or None
        pr["window_end"] = c.get("window_end") or None
        pr["confidence_tier"] = r.get("confidence_tier", "unrated")
        pr["interpretation"] = r.get("interpretation", "unreviewed")
        pr["notes"] = r.get("notes", "")
        ra = (r.get("radd_agree") or "").strip().lower()
        pr["radd_agree"] = True if ra == "true" else False if ra == "false" else None
        # separators are whitespace, ";" or "|" (documented in CONTRACTS.md); commas can be part of a URL
        pr["evidence_urls"] = [u for u in re.split(r"[\s;|]+", r.get("evidence_urls") or "") if u.startswith("http")]
    (C.WEB_DATA / "patches.geojson").write_text(json.dumps(gj))


def _hotspots():
    p = C.PROCESSED / "hotspots.geojson"
    if not p.exists():
        return _warn("hotspots.geojson")
    gj = json.loads(p.read_text())
    for ft in gj["features"]:
        ft["geometry"]["coordinates"] = [round(v, 5) for v in ft["geometry"]["coordinates"]]
        pr = ft["properties"]
        ft["properties"] = {"sensor": pr["sensor"], "acq_date": str(pr["acq_date"])[:10],
                            "confidence": pr["confidence"], "frp": pr["frp"]}
    (C.WEB_DATA / "hotspots.geojson").write_text(json.dumps(gj))


def _csv_to_json(src, dst, value_col):
    if not src.exists():
        return _warn(src.name)
    rows = [{"date": r["date"], "value": float(r[value_col])} for r in csv.DictReader(open(src)) if r[value_col] != ""]
    (C.WEB_DATA / dst).write_text(json.dumps(rows))


def main():
    C.WEB_DATA.mkdir(parents=True, exist_ok=True)
    manifest = {"fixture": bool(C.IS_FIXTURE_RUN),
                "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "study_bbox": C.BBOX_WGS84}
    inputs = {"stack": (C.INTERIM / "stack.nc").exists()}
    for key, name in (("patches", "patches.geojson"), ("timeseries", "timeseries.json"), ("hotspots", "hotspots.geojson"),
                      ("crosscheck", "crosscheck_stats.json"), ("review", "review.csv"), ("validation", "validation_stats.json"),
                      ("psi", "psi_daily.csv"), ("rain", "rain_daily.csv"), ("events", "eonet_events.geojson"),
                      ("peat", "peat_mask.tif")):
        inputs[key] = (C.PROCESSED / name).exists()
    manifest["inputs"] = inputs
    _overlays(manifest)
    _peat(manifest)
    if "dates" not in manifest:  # no radar stack yet: take dates from the config so the timeline still works
        manifest["dates"] = list(C.ACQ_DATES)
        manifest["overlays"] = {}
        manifest["bounds"] = [[C.BBOX_WGS84[1], C.BBOX_WGS84[0]], [C.BBOX_WGS84[3], C.BBOX_WGS84[2]]]
    _patches()
    _hotspots()
    # remove outputs whose inputs are gone, so a partial real run never mixes with old demo files
    for name, ok in (("patches.geojson", inputs["patches"]), ("hotspots.geojson", inputs["hotspots"]),
                     ("timeseries.json", inputs["timeseries"]), ("events.geojson", inputs["events"]),
                     ("psi.json", inputs["psi"]), ("rain.json", inputs["rain"])):
        if not ok and (C.WEB_DATA / name).exists():
            (C.WEB_DATA / name).unlink()
    if not inputs["stack"]:
        for old in (C.WEB_DATA / "overlays").glob("hv_*.png"):
            old.unlink()
    if not inputs["peat"] and (C.WEB_DATA / "overlays" / "peat.png").exists():
        (C.WEB_DATA / "overlays" / "peat.png").unlink()
    if inputs["timeseries"]:
        shutil.copy(C.PROCESSED / "timeseries.json", C.WEB_DATA / "timeseries.json")
    else:
        _warn("timeseries.json")
    if inputs["events"]:
        shutil.copy(C.PROCESSED / "eonet_events.geojson", C.WEB_DATA / "events.geojson")
    _csv_to_json(C.PROCESSED / "psi_daily.csv", "psi.json", "psi_24h_max")
    _csv_to_json(C.PROCESSED / "rain_daily.csv", "rain.json", "precip_mm")
    stats = {}
    for name, key in (("crosscheck_stats.json", "crosscheck"), ("validation_stats.json", "validation")):
        p = C.PROCESSED / name
        stats[key] = json.loads(p.read_text()) if p.exists() else None
    (C.WEB_DATA / "stats.json").write_text(json.dumps(stats, indent=1))
    (C.WEB_DATA / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"[S5] web/data updated ({'FIXTURE demo data' if C.IS_FIXTURE_RUN else 'real data'})")


if __name__ == "__main__":
    main()

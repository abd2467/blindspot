"""S3a: download FIRMS active-fire records and turn them into hotspots.geojson.

    python -m blindspot.s3_fire.firms download     # needs FIRMS_MAP_KEY in .env or the environment
    python -m blindspot.s3_fire.firms build        # raw CSVs -> data/processed/hotspots.geojson

The FIRMS area API returns at most a few days per call, so `download` walks the
season in 5-day steps for each source and logs which days it got in
data/raw/firms/coverage.json. The cross-check uses that log to mark patches
whose time window has missing fire data as "insufficient_data".

Status: download() follows the documented FIRMS area API URL pattern but has NOT
been run in this repo yet. WS3: run it first and fix anything the API rejects.
API docs: https://firms.modaps.eosdis.nasa.gov/api/area/
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from .. import config as C

API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{area}/{days}/{start}"
# Standard processing (_SP) is the quality-controlled archive; _NRT covers recent days it lacks.
SOURCES = [
    ("VIIRS_SNPP_SP", "VIIRS_SNPP_NRT"),
    ("VIIRS_NOAA20_SP", "VIIRS_NOAA20_NRT"),
    ("VIIRS_NOAA21_NRT", None),
    ("MODIS_SP", "MODIS_NRT"),
]
STEP_DAYS = 5
FIRMS_DIR = C.RAW / "firms"


def _key() -> str:
    key = os.environ.get("FIRMS_MAP_KEY")
    env = C.REPO_ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("FIRMS_MAP_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit("Set FIRMS_MAP_KEY (free key: https://firms.modaps.eosdis.nasa.gov/api/map_key/)")
    return key


def download():
    import requests

    key = _key()
    FIRMS_DIR.mkdir(parents=True, exist_ok=True)
    w, s, e, n = C.BBOX_WGS84
    area = f"{w - 0.05},{s - 0.05},{e + 0.05},{n + 0.05}"  # small margin for the buffer
    d0, d1 = date.fromisoformat(C.SEASON_START), date.fromisoformat(C.SEASON_END)
    coverage: dict[str, list[str]] = {}
    for primary, fallback in SOURCES:
        got = []
        day = d0
        while day <= d1:
            for src in (primary, fallback):
                if not src:
                    continue
                url = API.format(key=key, source=src, area=area, days=STEP_DAYS, start=day.isoformat())
                cached = FIRMS_DIR / f"{src}_{day.isoformat()}.csv"
                if cached.exists():
                    got += [(day + timedelta(i)).isoformat() for i in range(STEP_DAYS)]
                    break
                try:
                    r = requests.get(url, timeout=180)
                except requests.exceptions.RequestException as exc:
                    print(f"  {src} {day}: {exc.__class__.__name__}, skipping (rerun to retry)")
                    time.sleep(2)
                    continue
                ok = r.status_code == 200 and r.text.startswith("latitude")
                if ok:
                    out = FIRMS_DIR / f"{src}_{day.isoformat()}.csv"
                    out.write_text(r.text)
                    got += [(day + timedelta(i)).isoformat() for i in range(STEP_DAYS)]
                    break
                print(f"  {src} {day}: {r.status_code} {r.text[:80]!r}")
                time.sleep(1)
            day += timedelta(days=STEP_DAYS)
        coverage[primary.split("_SP")[0].split("_NRT")[0]] = sorted(set(got))
        print(f"{primary}: {len(set(got))} days covered")
    (FIRMS_DIR / "coverage.json").write_text(json.dumps(coverage, indent=1))


def build():
    """Merge every CSV in data/raw/firms into hotspots.geojson (EPSG:4326, clipped to the study box)."""
    w, s, e, n = C.BBOX_WGS84
    pad = 0.05
    feats, seen = [], set()
    for path in sorted(Path(FIRMS_DIR).glob("*.csv")):
        with open(path, newline="") as f:
            for r in csv.DictReader(f):
                lat, lon = float(r["latitude"]), float(r["longitude"])
                if not (w - pad <= lon <= e + pad and s - pad <= lat <= n + pad):
                    continue
                inst = r.get("instrument", "VIIRS" if "bright_ti4" in r else "MODIS").upper()
                sensor = "MODIS" if "MODIS" in inst else "VIIRS"
                k = (round(lat, 4), round(lon, 4), r["acq_date"], r["acq_time"], r.get("satellite"))
                if k in seen:
                    continue
                seen.add(k)
                feats.append({"type": "Feature",
                              "geometry": {"type": "Point", "coordinates": [lon, lat]},
                              "properties": {"sensor": sensor, "satellite": r.get("satellite", ""),
                                             "acq_date": r["acq_date"], "acq_time": r["acq_time"],
                                             "confidence": str(r.get("confidence", "")),
                                             "frp": float(r.get("frp") or 0),
                                             "source": "NRT" if "NRT" in r.get("version", "") else "SP"}})
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    (C.PROCESSED / "hotspots.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    print(f"[S3] {len(feats)} hotspots -> hotspots.geojson")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    {"download": download, "build": build}[cmd]()

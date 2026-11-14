"""S6: context data for the story: Singapore PSI and NASA EONET wildfire events.

    python -m blindspot.s6_context.context psi      # data.gov.sg PSI API, one call per day
    python -m blindspot.s6_context.context eonet    # NASA EONET wildfire events in a wider Kalimantan box

Outputs: data/processed/psi_daily.csv, data/processed/eonet_events.geojson
Status: request formats follow the public docs but have not been run from this repo yet.
"""
from __future__ import annotations

import csv
import json
import sys
import time
from datetime import date, timedelta

from .. import config as C

PSI_API = "https://api-open.data.gov.sg/v2/real-time/api/psi?date={d}"
EONET_API = "https://eonet.gsfc.nasa.gov/api/v3/events"
# Wider than the study box: the story map shows the regional fire season.
EONET_BBOX = (108.0, 1.0, 117.0, -5.0)  # min lon, max lat, max lon, min lat (EONET order)


def psi():
    import requests

    d0, d1 = date.fromisoformat(C.SEASON_START), date.fromisoformat(C.SEASON_END)
    rows = []
    day = d0
    while day <= d1:
        r = requests.get(PSI_API.format(d=day.isoformat()), timeout=30)
        best = None
        if r.ok:
            for item in r.json().get("data", {}).get("items", []):
                vals = item.get("readings", {}).get("psi_twenty_four_hourly", {})
                if vals:
                    best = max(best or 0, max(vals.values()))
        rows.append({"date": day.isoformat(), "psi_24h_max": "" if best is None else best, "region": "max_of_regions"})
        print(day, best)
        day += timedelta(days=1)
        time.sleep(0.3)
    with open(C.PROCESSED / "psi_daily.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "psi_24h_max", "region"])
        w.writeheader()
        w.writerows(rows)


def eonet():
    import requests

    params = {"category": "wildfires", "status": "all", "start": C.SEASON_START, "end": C.SEASON_END,
              "bbox": ",".join(str(v) for v in EONET_BBOX)}
    r = requests.get(EONET_API, params=params, timeout=60)
    r.raise_for_status()
    feats = []
    for ev in r.json().get("events", []):
        for g in ev.get("geometry", []):
            if g.get("type") != "Point":
                continue
            feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": g["coordinates"]},
                          "properties": {"id": ev["id"], "title": ev["title"], "date": g["date"][:10],
                                         "source": ",".join(s["id"] for s in ev.get("sources", []))}})
    (C.PROCESSED / "eonet_events.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    print(f"[S6] {len(feats)} EONET wildfire points")


if __name__ == "__main__":
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    {"psi": psi, "eonet": eonet}[sys.argv[1] if len(sys.argv) > 1 else "eonet"]()

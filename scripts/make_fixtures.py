"""Make a small synthetic data tree in data/fixtures/ that matches every contract.

Every workstream can build and test against these files before real data exists.
The synthetic scene is a 240 x 240 pixel (14.4 km) corner of the real grid with:

* peat-swamp forest with realistic L-band levels (HV about -12 dB, HH about -7 dB)
* multiplicative speckle (gamma, ENL 5)
* a river (water mask)
* fire scars that drop HV by 2 to 6 dB, some with FIRMS hotspots and some without
* clearings without fire, a flooded patch (HH rises), a wet-season shift on 28 Oct
* a small calibration jump on the last date (new processing version)

The truth table is saved so tests can score the pipeline. Run:

    python scripts/make_fixtures.py
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from blindspot import config as C  # noqa: E402
from blindspot.grid import coords, from_db  # noqa: E402

SEED = 2026
N = 240
ENL = 5.0
ROOT = C.FIXTURES


def d(s):
    return date.fromisoformat(s)


def main():
    import xarray as xr
    from pyproj import Transformer

    rng = np.random.default_rng(SEED)
    x, y = coords(shape=(N, N))
    X, Y = np.meshgrid(np.arange(N), np.arange(N))
    T = len(C.ACQ_DATES)

    # Base backscatter in dB with gentle spatial texture
    tex = rng.normal(0, 0.6, (N, N))
    from scipy.ndimage import gaussian_filter
    tex = gaussian_filter(tex, 6) * 4
    hv_db = np.repeat((-12.0 + tex)[None], T, 0)
    hh_db = np.repeat((-7.0 + 0.6 * tex)[None], T, 0)

    # River
    river = np.abs(Y - (60 + 25 * np.sin(X / 30.0))) < 3
    hv_db[:, river] = -22.0
    hh_db[:, river] = -18.0

    truth = []
    rng_events = np.random.default_rng(SEED + 1)

    def blob(cx, cy, r):
        rr = np.hypot(X - cx, Y - cy) + rng_events.normal(0, 0.8, (N, N))
        return rr < r

    # (kind, cx, cy, radius_px, date_index_of_first_change, hv_drop_db, has_hotspot)
    events = [
        ("fire", 40, 120, 9, 5, 4.5, True),
        ("fire", 90, 150, 6, 6, 3.5, True),
        ("fire", 150, 100, 12, 6, 5.0, True),
        ("fire", 200, 180, 7, 7, 4.0, False),   # under smoke: no hotspot recorded
        ("fire", 120, 210, 10, 7, 5.5, False),  # under smoke: no hotspot recorded
        ("fire", 60, 200, 5, 8, 3.0, True),
        ("fire", 210, 60, 8, 8, 4.0, False),    # smouldering peat: no hotspot
        ("fire", 175, 140, 4, 9, 6.0, True),
        ("clearing", 100, 30, 6, 5, 3.5, False),
        ("clearing", 30, 30, 5, 7, 3.0, False),
        ("flood", 180, 225, 6, 10, -1.0, False),  # HV mixed, HH rises
    ]
    for i, (kind, cx, cy, r, t0, drop, hs) in enumerate(events):
        m = blob(cx, cy, r) & ~river
        if kind == "flood":
            hh_db[t0:, m] += 3.0
            hv_db[t0:, m] -= 1.5
        else:
            hv_db[t0:, m] -= drop
            hh_db[t0:, m] -= drop * 0.35
        truth.append({"event_id": f"E{i:02d}", "kind": kind, "cx": cx, "cy": cy, "r_px": r,
                      "first_change_date": C.ACQ_DATES[t0], "hv_drop_db": drop,
                      "has_hotspot": hs, "area_ha": float(m.sum() * 0.36)})

    # Wet-season shift on the last date, plus calibration jump from the new processing version
    hv_db[-1] += 0.8 + 0.5
    hh_db[-1] += 1.2 + 0.5

    # Speckle: gamma with mean 1 and shape ENL
    def speckle(shape):
        return rng.gamma(ENL, 1.0 / ENL, shape)

    hv = (from_db(hv_db) * speckle(hv_db.shape)).astype("float32")
    hh = (from_db(hh_db) * speckle(hh_db.shape)).astype("float32")

    times = np.array(C.ACQ_DATES, dtype="datetime64[ns]")
    pv = ["P05023"] * (T - 1) + ["P05036"]
    ds = xr.Dataset(
        {"hh": (("time", "y", "x"), hh), "hv": (("time", "y", "x"), hv),
         "water": (("y", "x"), river.astype("uint8"))},
        coords={"time": times, "y": y, "x": x, "processing_version": ("time", pv)},
        attrs={"crs": C.CRS, "enl": ENL, "track": C.NISAR_TRACK, "frame": C.NISAR_FRAME,
               "fixture": 1, "notes": "SYNTHETIC demo data from scripts/make_fixtures.py"},
    )
    (ROOT / "interim").mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(ROOT / "interim" / "stack.nc")

    # ---- FIRMS-like hotspot CSVs ----------------------------------------
    to_ll = Transformer.from_crs(C.CRS, "EPSG:4326", always_xy=True)
    firms_dir = ROOT / "raw" / "firms"
    firms_dir.mkdir(parents=True, exist_ok=True)
    viirs_rows, modis_rows = [], []

    def add_hotspot(px, py, day, sensor):
        lon, lat = to_ll.transform(x[0] + px * C.RES_M, y[0] - py * C.RES_M)
        row = {"latitude": round(lat, 5), "longitude": round(lon, 5), "acq_date": day.isoformat(),
               "acq_time": f"{rng.choice([130, 545, 1810]):04d}", "frp": round(float(rng.uniform(2, 60)), 1),
               "daynight": "D", "version": "2.0NRT"}
        if sensor == "VIIRS":
            row.update(bright_ti4=330.0, scan=0.39, track=0.36, satellite=str(rng.choice(["N", "N20", "N21"])),
                       instrument="VIIRS", confidence=str(rng.choice(["n", "h", "l"])), bright_ti5=295.0)
            viirs_rows.append(row)
        else:
            row.update(brightness=320.0, scan=1.0, track=1.0, satellite=str(rng.choice(["Terra", "Aqua"])),
                       instrument="MODIS", confidence=int(rng.integers(30, 100)), bright_t31=295.0)
            modis_rows.append(row)

    for (kind, cx, cy, r, t0, drop, hs) in events:
        if not hs:
            continue
        start, end = d(C.ACQ_DATES[t0 - 1]), d(C.ACQ_DATES[t0])
        for _ in range(int(rng.integers(3, 9))):
            day = start + timedelta(days=int(rng.integers(1, (end - start).days + 1)))
            add_hotspot(cx + rng.normal(0, r / 2), cy + rng.normal(0, r / 2), day,
                        "VIIRS" if rng.random() < 0.75 else "MODIS")
    # Scattered small agricultural burns with no lasting radar change
    for _ in range(25):
        day = d(C.SEASON_START) + timedelta(days=int(rng.integers(0, 150)))
        add_hotspot(rng.uniform(0, N), rng.uniform(0, N), day, "VIIRS")

    for name, rows in (("viirs_fixture.csv", viirs_rows), ("modis_fixture.csv", modis_rows)):
        with open(firms_dir / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    # ---- Context tables ---------------------------------------------------
    proc = ROOT / "processed"
    proc.mkdir(parents=True, exist_ok=True)
    day0, day1 = d(C.SEASON_START), d(C.SEASON_END)
    days = [day0 + timedelta(days=i) for i in range((day1 - day0).days + 1)]
    with open(proc / "psi_daily.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "psi_24h_max", "region"])
        for dd in days:
            k = (dd - d("2026-10-09")).days
            base = 45 + 140 * np.exp(-(k / 18.0) ** 2) + (20 if d("2026-09-04") <= dd <= d("2026-10-25") else 0)
            w.writerow([dd.isoformat(), int(min(base + rng.normal(0, 5), 192)), "max_of_regions"])
    with open(proc / "rain_daily.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "precip_mm"])
        for dd in days:
            wet = dd >= d("2026-10-20")
            w.writerow([dd.isoformat(), round(float(rng.gamma(2, 6 if wet else 1.2)), 1)])
    lon_c, lat_c = to_ll.transform(x[N // 2], y[N // 2])
    events_gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(lon_c + dx, 4), round(lat_c + dy, 4)]},
         "properties": {"id": f"EONET_FIXTURE_{i}", "title": f"Wildfire, Central Kalimantan (demo {i})",
                        "date": dt, "source": "fixture"}}
        for i, (dx, dy, dt) in enumerate([(-0.03, 0.02, "2026-08-25"), (0.04, -0.01, "2026-09-15"),
                                          (0.01, 0.05, "2026-10-02")])]}
    (proc / "eonet_events.geojson").write_text(json.dumps(events_gj))

    # Reference labels for the accuracy sample (real ones are labelled by hand by WS4)
    (ROOT / "truth").mkdir(exist_ok=True)
    (ROOT / "truth" / "events.json").write_text(json.dumps(truth, indent=1))
    print(f"fixtures written to {ROOT}")


if __name__ == "__main__":
    main()

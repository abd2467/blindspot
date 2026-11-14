"""S3b: tag every radar-change patch by whether the hotspot record saw it, and compute the headline.

Inputs : data/processed/patches.geojson (WS2), data/processed/hotspots.geojson (S3a)
Outputs: data/processed/crosscheck.csv, data/processed/crosscheck_stats.json

Matching rule (all settings in config.PARAMS):
  A patch is "recorded" if at least one hotspot lies within `buffer_km` of the patch
  and was observed between the previous radar acquisition (minus `window_slack_days`)
  and the first-change date. Using the previous acquisition, not a fixed 12 days,
  accounts for real gaps such as the missing early-August date.
  "insufficient_data" means the fire record has missing days inside that window.

Headline: share of radar-change AREA with no recorded hotspot, with a Monte Carlo
range that jitters hotspot positions within the sensor footprint and draws the
buffer and slack from config ranges.

    python -m blindspot.s3_fire.crosscheck [--runs 300]
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, timedelta

import numpy as np

from .. import config as C


def _load():
    import geopandas as gpd

    patches = gpd.read_file(C.PROCESSED / "patches.geojson").to_crs(C.CRS)
    hs = gpd.read_file(C.PROCESSED / "hotspots.geojson").to_crs(C.CRS)
    # geopandas may parse date strings into datetimes; keep plain YYYY-MM-DD strings
    for col in ("first_change_date", "prev_acq_date"):
        patches[col] = patches[col].astype(str).str[:10]
    hs["acq_date"] = hs["acq_date"].astype(str).str[:10]
    hs["day"] = hs["acq_date"].map(lambda s: date.fromisoformat(str(s)[:10]).toordinal())
    cov_path = C.RAW / "firms" / "coverage.json"
    covered = None
    if cov_path.exists():
        cov = json.loads(cov_path.read_text())
        # a day counts as covered if at least one VIIRS source returned data
        covered = {d for k, days in cov.items() if "VIIRS" in k for d in days}
    return patches, hs, covered


def _windows(patches, slack_days):
    start = patches["prev_acq_date"].map(lambda s: date.fromisoformat(s).toordinal()) - slack_days
    end = patches["first_change_date"].map(lambda s: date.fromisoformat(s).toordinal())
    return start.to_numpy(), end.to_numpy()


def _candidate_pairs(patches, hs, max_dist_m):
    """(patch_idx, hotspot_idx) pairs that could ever match, to keep Monte Carlo fast."""
    import shapely

    tree = shapely.STRtree(hs.geometry.values)
    pi, hi = tree.query(patches.geometry.values, predicate="dwithin", distance=max_dist_m)
    return pi, hi


def match(patches, hs, buffer_km, slack_days, jitter=None, pairs=None):
    """Return per-patch hotspot counts and nearest distance (km) for one setting."""
    import shapely

    pi, hi = pairs
    pts = hs.geometry.values[hi]
    if jitter is not None:
        xy = shapely.get_coordinates(pts) + jitter[hi]
        pts = shapely.points(xy)
    dist = shapely.distance(patches.geometry.values[pi], pts)
    start, end = _windows(patches, slack_days)
    day = hs["day"].to_numpy()[hi]
    ok = (dist <= buffer_km * 1000) & (day >= start[pi]) & (day <= end[pi])
    n = np.bincount(pi[ok], minlength=len(patches))
    nearest = np.full(len(patches), np.nan)
    inwin = (day >= start[pi]) & (day <= end[pi])
    for p, dd in zip(pi[inwin], dist[inwin]):
        nearest[p] = dd if np.isnan(nearest[p]) else min(nearest[p], dd)
    return n, nearest / 1000.0


def run(runs: int = C.PARAMS["mc_runs"], seed: int = 0):
    patches, hs, covered = _load()
    P = C.PARAMS
    area_km2 = patches["area_ha"].to_numpy() / 100.0
    max_jit = max(P["footprint_half_m"].values())
    pairs = _candidate_pairs(patches, hs, P["mc_buffer_km"][1] * 1000 + max_jit)

    # ---- central estimate ------------------------------------------------
    n, nearest = match(patches, hs, P["buffer_km"], P["window_slack_days"], pairs=pairs)
    start, end = _windows(patches, P["window_slack_days"])
    status = np.where(n > 0, "recorded", "none").astype(object)
    if covered is not None:
        for i in range(len(patches)):
            days = {date.fromordinal(int(d)).isoformat() for d in range(start[i], end[i] + 1)}
            if status[i] == "none" and not days <= covered:
                status[i] = "insufficient_data"

    rows = []
    for i, pid in enumerate(patches["patch_id"]):
        rows.append({"patch_id": pid, "hotspot_status": status[i], "n_hotspots": int(n[i]),
                     "nearest_hotspot_km": "" if np.isnan(nearest[i]) else round(float(nearest[i]), 3),
                     "window_start": date.fromordinal(int(start[i])).isoformat(),
                     "window_end": date.fromordinal(int(end[i])).isoformat()})
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    with open(C.PROCESSED / "crosscheck.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else
                           ["patch_id", "hotspot_status", "n_hotspots", "nearest_hotspot_km", "window_start", "window_end"])
        w.writeheader()
        w.writerows(rows)

    eligible = status != "insufficient_data"
    total = float(area_km2[eligible].sum())
    none_km2 = float(area_km2[eligible & (status == "none")].sum())
    share = none_km2 / total if total else float("nan")

    # ---- Monte Carlo range ----------------------------------------------
    rng = np.random.default_rng(seed)
    half = np.array([P["footprint_half_m"][s] for s in hs["sensor"]])
    shares = []
    for _ in range(runs):
        jit = rng.uniform(-1, 1, (len(hs), 2)) * half[:, None]
        b = rng.uniform(*P["mc_buffer_km"])
        sl = int(rng.integers(P["mc_slack_days"][0], P["mc_slack_days"][1] + 1))
        n_r, _ = match(patches, hs, b, sl, jitter=jit, pairs=pairs)
        none = eligible & (n_r == 0)
        shares.append(area_km2[none].sum() / total if total else np.nan)
    shares = np.array(shares)

    # ---- per-date breakdown for the timeline -------------------------------
    by_date = []
    prev = date.fromisoformat(C.ACQ_DATES[0]) - timedelta(days=12)
    for d in C.ACQ_DATES:
        sel = (patches["first_change_date"] == d).to_numpy()
        dd = date.fromisoformat(d)
        n_hs = int(((hs["day"] > prev.toordinal()) & (hs["day"] <= dd.toordinal())).sum())
        by_date.append({"date": d, "change_km2": round(float(area_km2[sel].sum()), 3),
                        "no_hotspot_km2": round(float(area_km2[sel & (status == "none")].sum()), 3),
                        "n_hotspots": n_hs})
        prev = dd

    stats = {
        "total_change_km2": round(total, 3), "no_hotspot_km2": round(none_km2, 3),
        "no_hotspot_share": round(share, 4),
        "n_patches": int(len(patches)), "n_recorded": int((status == "recorded").sum()),
        "n_none": int((status == "none").sum()), "n_insufficient": int((status == "insufficient_data").sum()),
        "mc": {"p05": round(float(np.nanpercentile(shares, 5)), 4), "p50": round(float(np.nanpercentile(shares, 50)), 4),
               "p95": round(float(np.nanpercentile(shares, 95)), 4), "runs": runs},
        "params": {k: P[k] for k in ("buffer_km", "window_slack_days", "mc_buffer_km", "mc_slack_days", "footprint_half_m")},
        "by_date": by_date,
    }
    (C.PROCESSED / "crosscheck_stats.json").write_text(json.dumps(stats, indent=1))
    print(f"[S3] {stats['n_patches']} patches, {total:.2f} km2 changed, "
          f"{share:.0%} with no hotspot (MC 5-95%: {stats['mc']['p05']:.0%} to {stats['mc']['p95']:.0%})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=int, default=C.PARAMS["mc_runs"])
    run(ap.parse_args().runs)


if __name__ == "__main__":
    main()

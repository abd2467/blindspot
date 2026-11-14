"""Run every pipeline stage in order. This is the integration test.

    python scripts/run_pipeline.py --fixtures      # synthetic demo data, no logins needed (~10 s)
    python scripts/run_pipeline.py                 # real data (expects WS1/WS3/WS4/WS6 inputs in data/)
    python scripts/run_pipeline.py --from s3       # start at a later stage

Stages: s2 change -> s2 synthetic test -> s3 hotspots + cross-check -> s4 review/sample/stats -> s5 package.
S1 ingest and the downloads (FIRMS, PSI, EONET, RADD) are run separately by their owners,
because they need logins and network access.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sh(*args, env):
    print("$", " ".join(args), flush=True)
    subprocess.run([sys.executable, *args], check=True, env=env, cwd=ROOT)


def label_fixture_sample(env):
    """Fixture only: fill reference_sample.csv labels from the synthetic truth, standing in for human labelling."""
    code = r'''
import csv, json
from pyproj import Transformer
from blindspot import config as C
from blindspot.grid import coords
truth = json.load(open(C.FIXTURES / "truth" / "events.json"))
x, y = coords(shape=(240, 240))
to_utm = Transformer.from_crs("EPSG:4326", C.CRS, always_xy=True)
p = C.PROCESSED / "reference_sample.csv"
rows = list(csv.DictReader(open(p)))
for r in rows:
    ex, ey = to_utm.transform(float(r["lon"]), float(r["lat"]))
    col, row = (ex - x[0]) / C.RES_M, (y[0] - ey) / C.RES_M
    lab = "no_change"
    for e in truth:
        if ((col - e["cx"]) ** 2 + (row - e["cy"]) ** 2) ** 0.5 <= e["r_px"]:
            lab = {"fire": "burn"}.get(e["kind"], e["kind"])
    r["label"], r["labeller"] = lab, "fixture-truth"
w = csv.DictWriter(open(p, "w", newline=""), fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("[fixture] sample labelled from synthetic truth")
'''
    subprocess.run([sys.executable, "-c", code], check=True, env=env, cwd=ROOT)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fixtures", action="store_true", help="run on synthetic data in data/fixtures")
    ap.add_argument("--from", dest="start", default="s2", choices=["s2", "s3", "s4", "s5"])
    ap.add_argument("--method", default="omnibus", choices=["omnibus", "logratio"])
    a = ap.parse_args()
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    if a.fixtures:
        env["BLINDSPOT_DATA"] = "data/fixtures"
        if not (ROOT / "data/fixtures/interim/stack.nc").exists():
            sh("scripts/make_fixtures.py", env=env)
    order = ["s2", "s3", "s4", "s5"]
    todo = order[order.index(a.start):]
    if "s2" in todo:
        sh("-m", "blindspot.s2_change.detect", "--method", a.method, env=env)
        sh("-m", "blindspot.s2_change.synthetic", "--trials", "2", "--method", a.method, env=env)
    if "s3" in todo:
        sh("-m", "blindspot.s3_fire.firms", "build", env=env)
        sh("-m", "blindspot.s3_fire.crosscheck", env=env)
    if "s4" in todo:
        sh("-m", "blindspot.s4_validate.validate", "review", env=env)
        sh("-m", "blindspot.s4_validate.validate", "sample", env=env)
        if a.fixtures:
            label_fixture_sample(env)
        sh("-m", "blindspot.s4_validate.validate", "stats", env=env)
    if "s5" in todo:
        sh("-m", "blindspot.s5_package.package", env=env)
    sh("-m", "blindspot.contracts", "all", env=env)


if __name__ == "__main__":
    main()

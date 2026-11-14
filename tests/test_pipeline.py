"""End-to-end: fixtures -> pipeline -> every contract passes and the headline is sane."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_fixture_pipeline_runs_and_contracts_pass(tmp_path):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    subprocess.run([sys.executable, "scripts/run_pipeline.py", "--fixtures"], cwd=ROOT, env=env, check=True)
    stats = json.loads((ROOT / "web/data/stats.json").read_text())["crosscheck"]
    assert stats["n_patches"] > 0
    assert 0 <= stats["no_hotspot_share"] <= 1
    assert stats["mc"]["p05"] <= stats["mc"]["p95"]
    manifest = json.loads((ROOT / "web/data/manifest.json").read_text())
    assert manifest["fixture"] is True and len(manifest["dates"]) == 11

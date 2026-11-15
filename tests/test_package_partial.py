"""S5 packaging must cope with partial deliveries: the site deploys whatever has landed so far."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "data" / "fixtures" / "processed"


def _package(tmp_path, files):
    data = tmp_path / "data"
    (data / "processed").mkdir(parents=True)
    (data / "interim").mkdir()
    for f in files:
        shutil.copy(FIX / f, data / "processed" / f)
    web = tmp_path / "web_data"
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"),
               BLINDSPOT_DATA=str(data), BLINDSPOT_WEB_DATA=str(web))
    subprocess.run([sys.executable, "-m", "blindspot.s5_package.package"], check=True, env=env, cwd=ROOT)
    return web


def test_only_patches(tmp_path):
    """WS2 delivered, nothing else: dates and bounds fall back to config, stats are null."""
    if not (FIX / "patches.geojson").exists():
        return  # fixtures not built (run make fixtures)
    web = _package(tmp_path, ["patches.geojson", "timeseries.json"])
    m = json.loads((web / "manifest.json").read_text())
    assert m["inputs"]["patches"] and not m["inputs"]["stack"] and not m["inputs"]["crosscheck"]
    assert len(m["dates"]) == 11 and m["overlays"] == {} and len(m["bounds"]) == 2
    p = json.loads((web / "patches.geojson").read_text())["features"][0]["properties"]
    assert p["hotspot_status"] == "unknown" and p["radd_agree"] is None and p["evidence_urls"] == []
    assert json.loads((web / "stats.json").read_text()) == {"crosscheck": None, "validation": None}
    assert not (web / "hotspots.geojson").exists()


def test_all_tables(tmp_path):
    """Every small table delivered (no stack.nc): every field the app reads is present."""
    if not (FIX / "crosscheck.csv").exists():
        return
    files = [f.name for f in FIX.iterdir() if f.is_file()]
    web = _package(tmp_path, files)
    m = json.loads((web / "manifest.json").read_text())
    assert all(m["inputs"][k] for k in ("patches", "crosscheck", "review", "validation", "psi", "rain", "events"))
    p = json.loads((web / "patches.geojson").read_text())["features"][0]["properties"]
    for k in ("hotspot_status", "n_hotspots", "window_start", "window_end", "confidence_tier", "interpretation", "radd_agree"):
        assert k in p
    for f in ("psi.json", "rain.json", "events.geojson", "hotspots.geojson", "timeseries.json"):
        assert (web / f).exists()

"""Exercise WS2 public commands and hand-off contents without touching web/data."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
import xarray as xr

from blindspot import config as C
from blindspot.contracts import check_change, check_patches, check_timeseries
from blindspot.grid import coords, pixel_area_ha
from blindspot.s2_change.detect import make_patches


@pytest.fixture
def inputs(tmp_path):
    """Independent synthetic stack with a persistent drop and a last-date drop."""
    root = tmp_path / "fixtures"
    (root / "interim").mkdir(parents=True)
    rng = np.random.default_rng(90)
    shape = (len(C.ACQ_DATES), 64, 64)
    hh = rng.gamma(50, 0.2 / 50, shape)
    hv = rng.gamma(50, 0.05 / 50, shape)
    hh[5:, 15:27, 15:27] *= 0.5
    hv[5:, 15:27, 15:27] *= 0.2
    hv[-1, 40:50, 40:50] *= 0.1
    x, y = coords(shape=shape[1:])
    ds = xr.Dataset({"hh": (("time", "y", "x"), hh.astype("float32")),
                     "hv": (("time", "y", "x"), hv.astype("float32")),
                     "water": (("y", "x"), np.zeros(shape[1:], dtype="uint8"))},
                    coords={"time": np.array(C.ACQ_DATES, dtype="datetime64[ns]"),
                            "x": x, "y": y,
                            "processing_version": ("time", ["P05023"] * (shape[0] - 1) + ["P05036"])},
                    attrs={"enl": 50, "crs": C.CRS, "fixture": 1})
    ds.to_netcdf(root / "interim/stack.nc")
    env = dict(os.environ, PYTHONPATH=str(C.REPO_ROOT / "src"), BLINDSPOT_DATA=str(root))
    return root, env, ds


def command(env, module, *arguments, succeeds=True):
    """Run a public command, including strict numerical-warning handling."""
    result = subprocess.run([sys.executable, "-W", "error::RuntimeWarning", "-m",
                             f"blindspot.s2_change.{module}", *arguments],
                            env=env, capture_output=True, text=True)
    if succeeds:
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0, result.stdout
    return result


def read_json(path):
    """Reject nonstandard NaN and Infinity tokens accepted by Python by default."""
    def reject(token):
        raise ValueError(f"Nonfinite JSON value: {token}")
    return json.loads(path.read_text(), parse_constant=reject)


@pytest.mark.parametrize("arguments", [[], ["--method", "logratio", "--threshold", "auto"],
    ["--method", "logratio", "--threshold", "-2"], ["--method", "logratio", "--threshold", "-3"],
    ["--method", "logratio", "--threshold", "-4"], ["--smooth", "5"]])
def test_detection_commands_and_outputs(inputs, arguments):
    root, env, _ = inputs
    command(env, "detect", *arguments)
    path = root / "interim/change.nc"
    assert not check_change(path)
    assert not check_patches(root / "processed/patches.geojson")
    assert not check_timeseries(root / "processed/timeseries.json")
    with xr.open_dataset(path) as ch:
        first = ch.first_change.values
        assert ch.first_change.dtype == np.dtype("int16")
        assert ch.changed.dtype == np.dtype("uint8")
        assert ch.n_changed.dtype == np.dtype("int16")
        assert ch.p_value.dtype == ch.min_logratio_db.dtype == np.dtype("float32")
        assert (first[17:25, 17:25] == 5).mean() > 0.8
        assert (first[42:48, 42:48] == -1).all()
        np.testing.assert_array_equal(ch.changed.values, first >= 0)
        assert "minimum patch" in ch.attrs["method"]
        features = read_json(root / "processed/patches.geojson")["features"]
        assert sum(f["properties"]["area_ha"] for f in features) == pytest.approx(
            int(ch.changed.sum()) * pixel_area_ha(), abs=0.01 * len(features))
    ts = read_json(root / "processed/timeseries.json")
    assert set(ts["patches"]) == {f["properties"]["patch_id"] for f in features}
    assert all(f["properties"]["first_change_date"] > f["properties"]["prev_acq_date"] for f in features)
    assert all(len(v) == len(C.ACQ_DATES) for band in ts["patches"].values() for v in band.values())


@pytest.mark.parametrize("half", ["all", "west", "east"])
def test_sweep_preserves_selected_outputs(inputs, half):
    import csv

    root, env, _ = inputs
    command(env, "detect")
    paths = [root / "interim/change.nc", root / "processed/patches.geojson", root / "processed/timeseries.json"]
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    command(env, "sensitivity", "--half", half)
    after = [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    assert before == after
    with (root / "processed/s2_sensitivity.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 7
    assert all(r["half"] == half and r["fixture"] == "1" for r in rows)
    assert all(int(r["n_patches"]) >= 0 and float(r["change_area_ha"]) >= 0 for r in rows)
    assert {float(r["alpha"]) for r in rows if r["method"] == "omnibus"} == {0.001, 0.01, 0.05}
    assert {r["threshold_db"] for r in rows if r["method"] == "logratio"} == {"-2", "-3", "-4", "auto"}


@pytest.mark.parametrize("method", ["omnibus", "logratio"])
def test_synthetic_command_is_reproducible(inputs, method):
    root, env, _ = inputs
    command(env, "synthetic", "--method", method, "--trials", "1")
    path = root / "processed/synthetic_curve.json"
    before = path.read_bytes()
    command(env, "synthetic", "--method", method, "--trials", "1")
    assert before == path.read_bytes()
    out = read_json(path)
    assert out["method"] == method
    assert len(out["curve"]) == 24
    assert out["injected_date"] > max(C.REFERENCE_DATES)
    assert "FIXTURE" in out["note"]
    assert 0 <= out["false_alarm_rate"] <= 1
    for row in out["curve"]:
        assert row["trials"] in (0, 1)
        assert row["detection_rate"] is None if row["trials"] == 0 else 0 <= row["detection_rate"] <= 1


@pytest.mark.parametrize("module,arguments", [("detect", ["--alpha", "0"]),
    ("detect", ["--smooth", "2"]), ("detect", ["--method", "logratio", "--threshold", "1"]),
    ("synthetic", ["--trials", "0"])])
def test_bad_settings_fail_without_output(inputs, module, arguments):
    root, env, _ = inputs
    command(env, module, *arguments, succeeds=False)
    assert not (root / "processed").exists()


def test_stable_polygon_cli_and_all_patch_flags(inputs, monkeypatch):
    import geopandas as gpd
    from shapely.geometry import box

    root, env, ds = inputs
    polygon = root / "stable.geojson"
    x, y = ds.x.values, ds.y.values
    gpd.GeoDataFrame(geometry=[box(x[1], y[-2], x[10], y[1])], crs=C.CRS).to_crs("EPSG:4326").to_file(polygon, driver="GeoJSON")
    command(env, "detect", "--stable-area", str(polygon))
    with xr.open_dataset(root / "interim/change.nc") as ch:
        assert "stable polygon" in ch.attrs["method"]
    polygon.replace(root / "processed/stable_area.geojson")
    command(env, "detect")
    with xr.open_dataset(root / "interim/change.nc") as ch:
        assert "stable polygon" in ch.attrs["method"]
    first = np.full(ds.water.shape, -1, dtype="int16")
    first[0:4, 0:4] = len(C.ACQ_DATES) - 2
    ds.water.values[4, 2] = 1
    ds.hh.values[-2:, :4, :4] *= 4
    ds.coords["processing_version"] = ("time", ["P05023"] * (len(C.ACQ_DATES) - 2) + ["P05036"] * 2)
    monkeypatch.setattr(C, "PROCESSED", root / "flags")
    ch = xr.Dataset({"changed": (("y", "x"), first >= 0), "first_change": (("y", "x"), first),
                     "n_changed": (("y", "x"), np.full(first.shape, 2))})
    make_patches(ch, ds, np.zeros_like(ds.hv.values), C.ACQ_DATES)
    feature = read_json(C.PROCESSED / "patches.geojson")["features"][0]
    assert set(feature["properties"]["flags"]) == set(C.PATCH_FLAGS)


def test_no_change_produces_empty_valid_outputs(inputs):
    root, env, _ = inputs
    command(env, "detect", "--method", "logratio", "--threshold", "-100")
    assert read_json(root / "processed/patches.geojson")["features"] == []
    ts = read_json(root / "processed/timeseries.json")
    assert ts["patches"] == {}
    assert np.isfinite(ts["reference"]["hv_db"]).all()
    with xr.open_dataset(root / "interim/change.nc") as ch:
        assert not ch.changed.values.any()
        assert (ch.first_change.values == -1).all()

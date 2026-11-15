"""WS2 regressions for missing data, persistence, patch area and normalisation."""
import json

import numpy as np
import pytest
import xarray as xr

from blindspot import config as C
from blindspot.grid import coords, pixel_area_ha
from blindspot.s2_change.detect import (
    boxcar, detect_arrays, estimate_enl, filter_small_patches, load_stable_mask,
    make_patches, normalise_scene,
)
from blindspot.s2_change.omnibus import _band_terms, first_change
from blindspot.s2_change.sensitivity import summarise


def stack():
    """Stable speckle with enough land for robust scene statistics."""
    rng = np.random.default_rng(19)
    shape = (len(C.ACQ_DATES), 40, 40)
    return (0.2 * rng.gamma(50, 1 / 50, shape),
            0.05 * rng.gamma(50, 1 / 50, shape), np.zeros(shape[1:], dtype="uint8"))


@pytest.mark.parametrize("method", ["omnibus", "logratio"])
def test_persistent_drop_missing_pixels_and_last_date(method):
    hh, hv, water = stack()
    hv[5:, 4:12, 4:12] *= 0.2
    hh[5:, 4:12, 4:12] *= 0.6
    hv[-1, 20:28, 20:28] *= 0.1
    hv[6, 6, 6] = np.nan
    water[7, 7] = 1
    first, pval, _, _ = detect_arrays(hh, hv, water, C.ACQ_DATES, 0, method, smooth=1)
    assert (first[4:12, 4:12] == 5).mean() > 0.8
    assert first[6, 6] == first[7, 7] == -1
    assert np.isnan(pval[6, 6])
    assert (first[20:28, 20:28] < 0).all()


def test_patch_area_filter_uses_eight_connectivity():
    first = np.full((10, 10), -1, dtype="int16")
    min_pixels = int(np.ceil(C.PARAMS["min_patch_ha"] / pixel_area_ha()))
    for i in range(min_pixels):
        first[i, i] = 5
    first[-1, 0] = 5
    filtered = filter_small_patches(first)
    assert (filtered >= 0).sum() == min_pixels
    assert filtered[-1, 0] == -1


def test_stable_polygon_normalisation_preserves_widespread_change():
    a = np.ones((len(C.ACQ_DATES), 10, 10))
    stable = np.zeros((10, 10), bool)
    stable[:, :2] = True
    a[5:, :, 2:] *= 0.25
    a[5:] *= 2
    out = normalise_scene(a, C.ACQ_DATES, np.zeros((10, 10)), stable)
    np.testing.assert_allclose(out[5:, :, :2], 1)
    np.testing.assert_allclose(out[5:, :, 2:], 0.25)
    with pytest.raises(ValueError, match="stable area"):
        normalise_scene(a, C.ACQ_DATES, np.zeros((10, 10)), np.zeros((10, 10), bool))


def test_reference_looks_estimate_is_calibrated():
    rng = np.random.default_rng(5)
    a = rng.gamma(20, 1 / 20, (len(C.ACQ_DATES), 150, 150))
    measured = estimate_enl(a, C.ACQ_DATES, np.zeros((150, 150)))
    assert abs(measured - 20) < 1


def test_omnibus_factorisation_and_null_calibration():
    rng = np.random.default_rng(27)
    hh = rng.gamma(20, 0.2 / 20, (len(C.ACQ_DATES), 160, 160))
    hv = rng.gamma(20, 0.05 / 20, hh.shape)
    q, r = _band_terms(hv, 20)
    np.testing.assert_allclose(q, r.sum(axis=0), atol=1e-10)
    _, _, p_q = first_change(hh, hv, 20)
    # Independent null speckle, before directional and persistence restrictions.
    assert 0.006 < (p_q < C.PARAMS["omnibus_alpha"]).mean() < 0.016


def test_nan_filter_does_not_create_infinities():
    a = np.ones((3, 20, 20))
    a[:, :10, :10] = np.nan
    filtered = boxcar(a, 3)
    assert np.isnan(filtered[:, :8, :8]).all()
    assert np.isfinite(filtered[:, 11:, 11:]).all()
    assert not np.isinf(filtered).any()


def test_invalid_series_never_becomes_change():
    hh, hv, _ = stack()
    hv[5:, :4, :4] *= 0.1
    hv[3, :4, :4] = np.nan
    idx, pval, pq = first_change(hh, hv, 50)
    assert (idx[:4, :4] == -1).all()
    assert np.isnan(pval[:4, :4]).all()
    assert np.isnan(pq[:4, :4]).all()


def test_eligibility_can_select_later_persistent_drop():
    hh = np.full((len(C.ACQ_DATES), 1, 1), 0.2)
    hv = np.full_like(hh, 0.05)
    hv[2] *= 0.1
    hv[6:] *= 0.1
    eligible = np.zeros_like(hv, dtype=bool)
    eligible[6] = True
    idx, _, _ = first_change(hh, hv, 100, eligible=eligible)
    assert idx.item() == 6


def test_edge_flag_and_contracts(tmp_path, monkeypatch):
    from blindspot.contracts import check_patches, check_timeseries

    monkeypatch.setattr(C, "PROCESSED", tmp_path)
    hh, hv, water = stack()
    x, y = coords(shape=water.shape)
    ds = xr.Dataset({"hh": (("time", "y", "x"), hh),
                     "hv": (("time", "y", "x"), hv), "water": (("y", "x"), water)},
                    coords={"time": C.ACQ_DATES, "x": x, "y": y,
                            "processing_version": ("time", ["P05023"] * len(C.ACQ_DATES))})
    first = np.full(water.shape, -1, dtype="int16")
    first[:3, 4:8] = 5
    first[20:24, 20:24] = 5
    ds.hh.values[:, 19, 22] = np.nan
    ch = xr.Dataset({"changed": (("y", "x"), first >= 0),
                     "first_change": (("y", "x"), first),
                     "n_changed": (("y", "x"), np.full(water.shape, 4))})
    make_patches(ch, ds, np.zeros_like(hv), C.ACQ_DATES)
    path = tmp_path / "patches.geojson"
    features = json.loads(path.read_text())["features"]
    assert len(features) == 2
    assert all("edge" in f["properties"]["flags"] for f in features)
    assert not check_patches(path)
    assert not check_timeseries(tmp_path / "timeseries.json")


def test_empty_polygon_fails_instead_of_using_scene(tmp_path):
    path = tmp_path / "empty.geojson"
    path.write_text('{"type":"FeatureCollection","features":[]}')
    with pytest.raises(ValueError, match="polygons"):
        load_stable_mask(None, path)


def test_sensitivity_halves_partition_patches():
    x, y = coords()
    first = np.full(C.GRID_SHAPE, -1, dtype="int16")
    first[20:24, 20:24] = first[20:24, -24:-20] = 5
    count, area = summarise(first, x, y)
    west = summarise(first, x, y, "west")
    east = summarise(first, x, y, "east")
    assert west[0] == east[0] == 1
    assert count == west[0] + east[0]
    assert area == pytest.approx(west[1] + east[1])

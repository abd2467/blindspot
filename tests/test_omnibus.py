"""The omnibus test must keep its false-alarm rate on pure speckle and find a clear drop."""
import numpy as np

from blindspot.s2_change.omnibus import first_change


def _speckle(rng, shape, enl):
    return rng.gamma(enl, 1.0 / enl, shape)


def test_false_alarm_rate_on_no_change():
    rng = np.random.default_rng(0)
    k, n, enl = 11, 200, 20.0
    hh = 0.2 * _speckle(rng, (k, n, n), enl)
    hv = 0.05 * _speckle(rng, (k, n, n), enl)
    idx, _, _ = first_change(hh, hv, enl, alpha=0.01)
    rate = (idx >= 0).mean()
    assert rate < 0.03, rate  # first change over 10 tests, decreases only, gated by the omnibus Q


def test_detects_3db_drop_at_right_date():
    rng = np.random.default_rng(1)
    k, n, enl = 11, 50, 40.0
    hh = 0.2 * _speckle(rng, (k, n, n), enl)
    hv = 0.05 * _speckle(rng, (k, n, n), enl)
    hv[6:] *= 10 ** (-0.3)
    hh[6:] *= 10 ** (-0.1)
    idx, _, _ = first_change(hh, hv, enl, alpha=0.01)
    assert (idx == 6).mean() > 0.8

"""Sequential omnibus change test for dual-pol (HH, HV) intensity time series.

Follows Conradsen et al. (2016) for the diagonal (dual-pol intensity) case used by
Canty et al. (2020). For each band with equivalent number of looks m and
intensities X_1..X_k (linear power):

    ln Q   = m * ( k ln k + sum_i ln X_i - k ln S_k )                 # omnibus: "no change at all"
    ln R_j = m * ( j ln j - (j-1) ln(j-1) + (j-1) ln S_{j-1}
                   + ln X_j - j ln S_j )                              # "change at image j"

with S_j = X_1 + ... + X_j. The two bands are independent, so their log
statistics add. Under no change, -2 ln Q ~ chi2(2(k-1)) and -2 ln R_j ~ chi2(2)
(first-order approximation, no small-sample correction).

This version finds the FIRST change for each pixel, testing from the first image.
That is all Blindspot needs (first-change date). Status: implemented and checked
on synthetic data only (see tests/test_omnibus.py). WS2 owns any refinement.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import chi2


def _band_terms(X: np.ndarray, m: float):
    """X: (k, ny, nx) linear intensities. Returns ln Q (ny, nx) and ln R_j (k-1, ny, nx) for j=2..k."""
    k = X.shape[0]
    X = np.clip(X, 1e-10, None).astype("float64")
    S = np.cumsum(X, axis=0)
    lnX = np.log(X)
    lnQ = m * (k * np.log(k) + lnX.sum(0) - k * np.log(S[-1]))
    j = np.arange(2, k + 1, dtype="float64")[:, None, None]
    lnR = m * (j * np.log(j) - (j - 1) * np.log(j - 1) + (j - 1) * np.log(S[:-1]) + lnX[1:] - j * np.log(S[1:]))
    return lnQ, lnR


def first_change(hh: np.ndarray, hv: np.ndarray, enl: float, alpha: float = 0.01):
    """Return (first_change_index, p_value_at_change, omnibus_p).

    first_change_index is the image index (0-based) of the first significant change,
    or -1 where none. Only HV decreases count as change (canopy loss), so a change is
    kept only if HV at that image is lower than the mean of the images before it.
    """
    k = hv.shape[0]
    lq_hh, lr_hh = _band_terms(hh, enl)
    lq_hv, lr_hv = _band_terms(hv, enl)
    q_stat = -2 * (lq_hh + lq_hv)
    p_q = chi2.sf(q_stat, 2 * (k - 1))
    r_stat = -2 * (lr_hh + lr_hv)
    p_r = chi2.sf(r_stat, 2)

    prev_mean = np.cumsum(hv, axis=0)[:-1] / np.arange(1, k)[:, None, None]
    decrease = hv[1:] < prev_mean
    sig = (p_r < alpha) & decrease & (p_q < alpha)[None]
    has = sig.any(0)
    idx = np.where(has, sig.argmax(0) + 1, -1)
    p_at = np.where(has, np.take_along_axis(p_r, np.clip(idx - 1, 0, None)[None], 0)[0], np.nan)
    return idx.astype("int16"), p_at.astype("float32"), p_q.astype("float32")

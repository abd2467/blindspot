"""Synthetic burn test: how small and how faint a burn can the detector find here?

Takes the real stack, picks stable pixels (no detected change, not water), and
injects square "burns" that lower HV by 2 to 6 dB (HH by 35% of that in dB) from
one date onward. Multiplying the real intensities keeps the real speckle, so the
noise is exactly what the detector faces. Then it reruns the detector and records:

* detection rate per (drop, size): share of injected burns with at least half
  their pixels flagged, with the first-change date within one acquisition
* false-alarm rate: share of untouched stable pixels flagged as changed

Output: data/processed/synthetic_curve.json (merged into stats.json by S5).
The smallest size with detection rate >= 0.8 at a 3 dB drop is a good minimum patch size.

    python -m blindspot.s2_change.synthetic [--trials 3] [--method omnibus]
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from .. import config as C
from ..grid import pixel_area_ha
from .detect import detect_arrays

SIZES_HA = [1, 2, 5, 10, 20, 50]
DROPS_DB = [2, 3, 4, 6]


def run(trials: int = 3, method: str = "omnibus", seed: int = 7):
    import xarray as xr

    ds = xr.open_dataset(C.INTERIM / "stack.nc")
    times = [str(t)[:10] for t in ds.time.values]
    hh0, hv0 = ds.hh.values.astype("float64"), ds.hv.values.astype("float64")
    water = ds.water.values
    enl = ds.attrs["enl"]
    base_first, *_ = detect_arrays(hh0, hv0, water, times, enl, method)
    stable = (water == 0) & (base_first < 0)
    from scipy.ndimage import binary_erosion
    stable_core = binary_erosion(stable, iterations=3)
    rng = np.random.default_rng(seed)
    t_inj = len(times) // 2 + 1  # inject mid-season so persistence can be tested
    ny, nx = stable.shape
    sides = {s: max(1, int(round(np.sqrt(s / pixel_area_ha())))) for s in SIZES_HA}

    hits = {(d, s): [] for d in DROPS_DB for s in SIZES_HA}
    fa = []
    for _ in range(trials):
        for drop in DROPS_DB:
            hh, hv = hh0.copy(), hv0.copy()
            injected = np.zeros((ny, nx), bool)
            boxes = []
            for s in SIZES_HA:
                side = sides[s]
                for _try in range(200):
                    r, c = int(rng.integers(0, ny - side)), int(rng.integers(0, nx - side))
                    win = (slice(r, r + side), slice(c, c + side))
                    pad = (slice(max(r - 4, 0), r + side + 4), slice(max(c - 4, 0), c + side + 4))
                    if stable_core[win].all() and not injected[pad].any():
                        break
                else:
                    continue  # scene too small for this size; skipped
                injected[win] = True
                hv[t_inj:, win[0], win[1]] *= 10 ** (-drop / 10)
                hh[t_inj:, win[0], win[1]] *= 10 ** (-0.35 * drop / 10)
                boxes.append((s, win))
            first, *_ = detect_arrays(hh, hv, water, times, enl, method)
            for s, win in boxes:
                f = first[win]
                ok = (f >= 0) & (np.abs(f - t_inj) <= 1)
                hits[(drop, s)].append(ok.mean() >= 0.5)
            untouched = stable & ~injected
            fa.append(float((first[untouched] >= 0).mean()))

    curve = [{"drop_db": d, "size_ha": s, "trials": len(v),
              "detection_rate": round(float(np.mean(v)), 3) if v else None}
             for (d, s), v in hits.items()]
    out = {"method": method, "injected_date": times[t_inj], "curve": curve,
           "false_alarm_rate": round(float(np.mean(fa)), 5),
           "note": "Burns injected into real stable pixels; speckle is the real data's own."}
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    (C.PROCESSED / "synthetic_curve.json").write_text(json.dumps(out, indent=1))
    print(f"[S2 synthetic] false-alarm rate {out['false_alarm_rate']:.4f}")
    for d in DROPS_DB:
        row = "  ".join(f"{s:>3}ha:{np.mean(hits[(d, s)]) if hits[(d, s)] else float('nan'):.2f}" for s in SIZES_HA)
        print(f"  drop {d} dB  {row}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--method", choices=["omnibus", "logratio"], default="omnibus")
    a = ap.parse_args()
    run(a.trials, a.method)


if __name__ == "__main__":
    main()

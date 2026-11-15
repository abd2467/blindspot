"""Run the WS2 parameter sweep without overwriting the selected detection outputs.

Usage: python -m blindspot.s2_change.sensitivity [--half west|east|all]
"""
from __future__ import annotations

import argparse
import csv

import numpy as np

from .. import config as C
from ..grid import pixel_area_ha
from .detect import detect_arrays, load_stable_mask


def summarise(first, x, y, half="all"):
    """Count 8-connected patches and their area, selecting by centroid longitude."""
    from pyproj import Transformer
    from scipy.ndimage import center_of_mass, label

    labels, count = label(first >= 0, structure=np.ones((3, 3)))
    if count == 0:
        return 0, 0.0
    ids = np.arange(1, count + 1)
    sizes = np.bincount(labels.ravel())[1:]
    if half != "all":
        centers = np.array(center_of_mass(np.ones(first.shape), labels, ids))
        cols = np.interp(centers[:, 1], np.arange(len(x)), x)
        rows = np.interp(centers[:, 0], np.arange(len(y)), y)
        lon, _ = Transformer.from_crs(C.CRS, "EPSG:4326", always_xy=True).transform(cols, rows)
        midpoint = (C.BBOX_WGS84[0] + C.BBOX_WGS84[2]) / 2
        selected = lon < midpoint if half == "west" else lon >= midpoint
        sizes = sizes[selected]
    return len(sizes), float(sizes.sum() * pixel_area_ha())


def run(half="all", smooth=3, stable_area=None):
    """Write seven sensitivity settings, retaining the shared production defaults."""
    import xarray as xr

    rows = []
    settings = [("omnibus", alpha, C.PARAMS["logratio_threshold_db"]) for alpha in (0.001, C.PARAMS["omnibus_alpha"], 0.05)]
    settings += [("logratio", C.PARAMS["omnibus_alpha"], threshold) for threshold in (-2, -3, -4, "auto")]
    with xr.open_dataset(C.INTERIM / "stack.nc") as ds:
        times = [str(t)[:10] for t in ds.time.values]
        hh, hv, water = ds.hh.values, ds.hv.values, ds.water.values
        stable = load_stable_mask(ds, stable_area)
        for method, alpha, threshold in settings:
            first, _, _, description = detect_arrays(hh, hv, water, times, ds.attrs["enl"],
                                                     method, threshold, alpha, smooth, stable)
            count, area = summarise(first, ds.x.values, ds.y.values, half)
            rows.append(dict(method=method, alpha=alpha, threshold_db=threshold, smooth=smooth,
                             half=half, n_patches=count, change_area_ha=round(area, 4),
                             fixture=int(ds.attrs.get("fixture", 0)), settings=description))
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    path = C.PROCESSED / "s2_sensitivity.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"[S2 sensitivity] {len(rows)} settings written to {path}")
    return rows


def main():
    """Parse sweep options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--half", choices=["west", "east", "all"], default="all")
    parser.add_argument("--smooth", type=int, default=3)
    parser.add_argument("--stable-area")
    args = parser.parse_args()
    run(args.half, args.smooth, args.stable_area)


if __name__ == "__main__":
    main()

"""S1: NISAR GCOV granules -> data/interim/stack.nc on the shared 60 m grid.

    python -m blindspot.s1_ingest.ingest search      # list matching granules, write data/raw/granules.json
    python -m blindspot.s1_ingest.ingest build       # stream the study-area subset of each, build stack.nc

Needs a free Earthdata login (earthaccess reads ~/.netrc or EARTHDATA_USERNAME / EARTHDATA_PASSWORD).

How it avoids downloading 5 GB per granule: earthaccess.open() gives a remote file
object, h5py reads only the HDF5 chunks inside the study-area window, and that
window is averaged onto the 60 m grid with rasterio (average resampling does the
multilooking and any reprojection in one step).

Status: written against the NISAR GCOV product layout in the Data User Guide but
NOT yet run against a real granule. WS1, before anything else:
  1. run `search` and check the printed names really are track 061, frame 090, 4005_DHDH
  2. open one granule and confirm the HDF5 paths in GCOV_PATHS (h5py: f.visit(print))
  3. run `build --limit 2` and look at the result before running all dates
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from .. import config as C
from ..grid import coords, transform_from_coords

# HDF5 dataset paths inside a GCOV granule. CHECK THESE against a real file (step 2 above).
GCOV_PATHS = {
    "hh": "/science/LSAR/GCOV/grids/frequencyA/HHHH",
    "hv": "/science/LSAR/GCOV/grids/frequencyA/HVHV",
    "x": "/science/LSAR/GCOV/grids/frequencyA/xCoordinates",
    "y": "/science/LSAR/GCOV/grids/frequencyA/yCoordinates",
    "epsg": "/science/LSAR/GCOV/grids/frequencyA/projection",
}


def search():
    import earthaccess

    earthaccess.login()
    found = []
    for short in (C.GCOV_PROVISIONAL, C.GCOV_VALIDATED):
        res = earthaccess.search_data(short_name=short, bounding_box=C.BBOX_WGS84,
                                      temporal=(C.ACQ_DATES[0], C.ACQ_DATES[-1] + "T23:59:59"))
        for g in res:
            name = g["umm"]["GranuleUR"]
            if C.GRANULE_MUST_CONTAIN not in name:
                continue
            urls = [u["URL"] for u in g["umm"].get("RelatedUrls", []) if u["URL"].endswith(".h5")]
            found.append({"collection": short, "name": name, "urls": urls,
                          "start": g["umm"]["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"]})
    found.sort(key=lambda r: r["start"])
    C.RAW.mkdir(parents=True, exist_ok=True)
    (C.RAW / "granules.json").write_text(json.dumps(found, indent=1))
    for r in found:
        print(r["start"][:10], r["name"])
    print(f"{len(found)} dual-pol granules. Keep only track {C.NISAR_TRACK:03d} {C.NISAR_DIRECTION} "
          f"frame {C.NISAR_FRAME:03d}: edit data/raw/granules.json by hand if other tracks appear.")


def _read_window(h5, dst_bounds):
    """Read the part of one GCOV grid that covers dst_bounds (in the granule's own CRS)."""
    x = h5[GCOV_PATHS["x"]][:]
    y = h5[GCOV_PATHS["y"]][:]
    xmin, ymin, xmax, ymax = dst_bounds
    pad = 200.0
    cols = np.where((x >= xmin - pad) & (x <= xmax + pad))[0]
    rows = np.where((y >= ymin - pad) & (y <= ymax + pad))[0]
    if cols.size == 0 or rows.size == 0:
        raise ValueError("granule does not cover the study area")
    r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
    hh = h5[GCOV_PATHS["hh"]][r0:r1, c0:c1].astype("float32")
    hv = h5[GCOV_PATHS["hv"]][r0:r1, c0:c1].astype("float32")
    return hh, hv, x[c0:c1], y[r0:r1]


def build(limit: int | None = None):
    import earthaccess
    import h5py
    import xarray as xr
    from rasterio.crs import CRS
    from rasterio.warp import Resampling, reproject, transform_bounds

    earthaccess.login()
    gr = json.loads((C.RAW / "granules.json").read_text())[:limit]
    gx, gy = coords()
    dst_tf = transform_from_coords(gx, gy)
    dst_crs = CRS.from_string(C.CRS)
    stack_hh, stack_hv, times, versions = [], [], [], []
    for r in gr:
        print("reading", r["name"])
        fobj = earthaccess.open([r["urls"][0]])[0]
        with h5py.File(fobj, "r") as h5:
            epsg = int(np.asarray(h5[GCOV_PATHS["epsg"]]).item())
            src_crs = CRS.from_epsg(epsg)
            b = transform_bounds(dst_crs, src_crs, *C.GRID_BOUNDS)
            hh, hv, x, y = _read_window(h5, b)
        fobj.close()
        res = abs(float(x[1] - x[0]))
        src_tf = transform_from_coords(x, y, res=res)
        out = []
        for band in (hh, hv):
            band = np.where(band > 0, band, np.nan)
            dst = np.full(C.GRID_SHAPE, np.nan, "float32")
            reproject(band, dst, src_transform=src_tf, src_crs=src_crs, dst_transform=dst_tf,
                      dst_crs=dst_crs, resampling=Resampling.average, src_nodata=np.nan, dst_nodata=np.nan)
            out.append(dst)
        stack_hh.append(out[0])
        stack_hv.append(out[1])
        times.append(r["start"][:10])
        versions.append(next((p for p in r["name"].split("_") if p.startswith("P0")), "unknown"))

    hv_arr = np.stack(stack_hv)
    # Water: WS1 replaces this with the NISAR_WATERMASK product. Fallback: very dark HV in every date.
    water = (np.nanmedian(10 * np.log10(hv_arr), axis=0) < -20).astype("uint8")
    ds = xr.Dataset(
        {"hh": (("time", "y", "x"), np.stack(stack_hh)), "hv": (("time", "y", "x"), hv_arr),
         "water": (("y", "x"), water)},
        coords={"time": np.array(times, dtype="datetime64[ns]"), "y": gy, "x": gx,
                "processing_version": ("time", versions)},
        attrs={"crs": C.CRS, "enl": 0.0, "track": C.NISAR_TRACK, "frame": C.NISAR_FRAME, "fixture": 0,
               "notes": "enl=0 means unknown; S2 estimates the effective looks from the reference dates."},
    )
    C.INTERIM.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(C.INTERIM / "stack.nc")
    print(f"stack.nc written: {len(times)} dates, grid {C.GRID_SHAPE}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["search", "build"])
    ap.add_argument("--limit", type=int, default=None, help="only the first N granules (for testing)")
    a = ap.parse_args()
    search() if a.cmd == "search" else build(a.limit)


if __name__ == "__main__":
    sys.exit(main())

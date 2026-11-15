"""Add the NISAR reference water mask to a copy of the existing radar stack.

Run from the project root:
    python -m blindspot.s1_ingest.watermask

Writes data/interim/stack_watermask.nc; leaves stack.nc unchanged.
"""
from pathlib import Path
import os
import tempfile

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
import xarray as xr

from .. import config as C
from ..grid import coords, transform_from_coords


TILE_NAMES = (
    "NISAR_water_mask_S3_S2_E112_E113_30m_v0.5.0.tif",
    "NISAR_water_mask_S4_S3_E112_E113_30m_v0.5.0.tif",
)


def build_water_mask(x, y):
    """Reproject categorical tiles separately and combine on the shared grid."""
    shape = (len(y), len(x))
    combined = np.full(shape, 255, dtype="uint8")
    dst_transform = transform_from_coords(x, y)
    for name in TILE_NAMES:
        path = Path(C.RAW) / name
        if not path.is_file():
            raise FileNotFoundError(f"Missing water-mask tile: {path}")
        with rasterio.open(path) as src:
            if src.count != 1 or src.crs is None:
                raise ValueError(f"Expected one georeferenced band: {name}")
            if src.nodata != 255 or src.dtypes[0] != "uint8":
                raise ValueError(f"Unexpected type or NoData in {name}")
            tile = np.full(shape, 255, dtype="uint8")
            reproject(
                source=rasterio.band(src, 1), destination=tile,
                src_transform=src.transform, src_crs=src.crs,
                src_nodata=255, dst_transform=dst_transform,
                dst_crs=C.CRS, dst_nodata=255,
                resampling=Resampling.nearest,
            )
        valid = tile != 255
        if np.any(valid & (tile > 200)):
            raise ValueError(f"Reserved classes found on study grid in {name}")
        overlap = valid & (combined != 255)
        if np.any(tile[overlap] != combined[overlap]):
            raise ValueError("Water-mask tiles disagree in their overlap")
        combined[valid] = tile[valid]
    missing = int(np.count_nonzero(combined == 255))
    if missing:
        raise ValueError(
            f"Water-mask source missing at {missing} study-grid pixels; "
            "no output written. Do not interpret missing data as land."
        )
    return ((combined >= 1) & (combined <= 200)).astype("uint8")


def main():
    source = Path(C.INTERIM) / "stack.nc"
    output = Path(C.INTERIM) / "stack_watermask.nc"
    with xr.open_dataset(source) as opened:
        ds = opened.load()
    x, y = coords()
    if ds.attrs.get("crs") != C.CRS:
        raise ValueError("Stack CRS does not match project configuration")
    if (ds.sizes.get("x"), ds.sizes.get("y")) != (len(x), len(y)):
        raise ValueError("Stack dimensions do not match the shared grid")
    if not (np.allclose(ds.x.values, x, rtol=0, atol=1e-6)
            and np.allclose(ds.y.values, y, rtol=0, atol=1e-6)):
        raise ValueError("Stack coordinates do not match the shared grid")
    water = build_water_mask(x, y)
    ds["water"] = xr.DataArray(
        water, dims=("y", "x"), coords={"y": ds.y, "x": ds.x},
        attrs={
            "long_name": "NISAR v0.5.0 reference water mask",
            "flag_values": np.array([0, 1], dtype="uint8"),
            "flag_meanings": "non_water reference_water",
            "source_files": "; ".join(TILE_NAMES),
        },
    )
    note = (
        "HH/HV are linear gamma0 (gamma-naught) power. "
        "Water: NISAR_WATERMASK v0.5.0, two EPSG:4326 tiles, "
        "nearest-neighbour resampling to the shared grid; "
        "source classes 1-200 mapped to 1, source 0 mapped to 0. "
        "No source missing or reserved classes on the output grid. "
        "Reference water classification; permanence not verified. "
        "Radar NaNs remain invalid independently of the water mask. "
        "Western radar coverage gap and dark edge require downstream masking."
    )
    previous = str(ds.attrs.get("notes", "")).strip()
    ds.attrs["notes"] = (previous + " " + note).strip()
    ds.attrs["water_mask_source"] = "NISAR_WATERMASK v0.5.0"
    ds.attrs["water_mask_method"] = "source classes 1-200; nearest-neighbour"

    # Write and verify a temporary file before replacing any previous candidate.
    fd, temp_name = tempfile.mkstemp(suffix=".nc", dir=output.parent)
    os.close(fd)
    try:
        ds.to_netcdf(temp_name)
        with xr.open_dataset(temp_name) as check:
            if check.water.dtype != np.dtype("uint8"):
                raise ValueError("Output water dtype is not uint8")
            if not np.array_equal(check.water.values, water):
                raise ValueError("Saved water mask differs from computed mask")
            for band in ("hh", "hv"):
                if not np.array_equal(check[band].values, ds[band].values,
                                      equal_nan=True):
                    raise ValueError(f"Saved {band} data changed unexpectedly")
        os.replace(temp_name, output)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        ds.close()
    print(f"Written: {output}")
    print(f"Reference water: {100 * water.mean():.2f}% of the shared grid")
    print("Original stack.nc unchanged. Next run:")
    print("python -m blindspot.contracts stack data/interim/stack_watermask.nc")


if __name__ == "__main__":
    main()

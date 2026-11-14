"""Helpers for the shared analysis grid (EPSG:32749, 60 m, north-up)."""
from __future__ import annotations

import numpy as np

from . import config as C


def coords(shape=C.GRID_SHAPE, bounds=C.GRID_BOUNDS, res=C.RES_M):
    """Pixel-centre x and y coordinates. y decreases downwards (north-up)."""
    xmin, _, _, ymax = bounds
    ny, nx = shape
    x = xmin + res / 2 + res * np.arange(nx)
    y = ymax - res / 2 - res * np.arange(ny)
    return x, y


def transform_from_coords(x, y, res=C.RES_M):
    """Affine transform for rasterio from pixel-centre coordinates."""
    from rasterio.transform import from_origin

    return from_origin(float(x[0]) - res / 2, float(y[0]) + res / 2, res, res)


def pixel_area_ha(res=C.RES_M) -> float:
    return res * res / 10_000.0


def to_db(a):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10.0 * np.log10(a)


def from_db(a):
    return 10.0 ** (np.asarray(a) / 10.0)

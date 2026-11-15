"""Shared constants for every workstream.

This file is the single source of truth for the study area, grid, dates,
file paths and default parameters. Change it only through a pull request
that the integration lead approves (see docs/CONTRACTS.md, "Changing a contract").
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
# Set BLINDSPOT_DATA=data/fixtures to run everything on synthetic demo data.
DATA = REPO_ROOT / os.environ.get("BLINDSPOT_DATA", "data")
IS_FIXTURE_RUN = "fixtures" in str(DATA)
RAW = DATA / "raw"            # downloads, never committed
INTERIM = DATA / "interim"    # stack.nc, change.nc, never committed
PROCESSED = DATA / "processed"  # small tables and GeoJSON passed between workstreams
FIXTURES = REPO_ROOT / "data" / "fixtures"  # synthetic data tree made by scripts/make_fixtures.py
WEB_DATA = REPO_ROOT / os.environ.get("BLINDSPOT_WEB_DATA", "web/data")  # what the web app reads (committed, kept small)

# ---------------------------------------------------------------------------
# Study area and grid
# ---------------------------------------------------------------------------
# A 50 x 50 km box near Sampit, Central Kalimantan, centred on the 2026 EONET
# wildfire cluster (about 112.6 E, 2.9 S). WS1 must confirm that NISAR track 061
# descending, frame 090 covers it before Gate 1.
BBOX_WGS84 = (112.375, -3.125, 112.825, -2.675)  # (west, south, east, north)

CRS = "EPSG:32749"   # WGS 84 / UTM zone 49S, metres
RES_M = 60.0         # analysis pixel size after multilooking
# Pixel-edge bounds of the analysis grid in CRS units. 833 x 833 pixels.
GRID_BOUNDS = (652_860.0, 9_654_360.0, 702_840.0, 9_704_340.0)  # (xmin, ymin, xmax, ymax)
GRID_SHAPE = (833, 833)  # (rows = y, cols = x)

# ---------------------------------------------------------------------------
# NISAR acquisitions (track 061 descending, frame 090), checked in CMR 14 Nov 2026
# ---------------------------------------------------------------------------
NISAR_TRACK = 61
NISAR_DIRECTION = "descending"
NISAR_FRAME = 90
ACQ_DATES = [
    "2026-06-18", "2026-06-30", "2026-07-12", "2026-07-24",
    # early-August acquisition (cycle 27) is missing from the archive
    "2026-08-17", "2026-08-29", "2026-09-10", "2026-09-22",
    "2026-10-04", "2026-10-16", "2026-10-28",
]
# Dates averaged to form the "before" reference. Chosen from the local event
# timeline, not assumed to be undisturbed: WS2 checks the reference area for
# change inside these dates and drops any that already show disturbance.
REFERENCE_DATES = ["2026-06-18", "2026-06-30", "2026-07-12", "2026-07-24"]
GCOV_PROVISIONAL = "NISAR_L2_GCOV_PROVISIONAL_V1"  # 18 Jun to 16 Oct, processing P05023
GCOV_VALIDATED = "NISAR_L2_GCOV_V1"                # 28 Oct onward, processing P05036
SOIL_MOISTURE = "NISAR_L3_SME2_PROVISIONAL_V1"
GRANULE_MUST_CONTAIN = "4005_DHDH"  # dual-pol only; skip SHSH single-pol granules

# ---------------------------------------------------------------------------
# Season window for fire records and context data
# ---------------------------------------------------------------------------
SEASON_START = "2026-06-01"
SEASON_END = "2026-11-10"

# ---------------------------------------------------------------------------
# Default analysis parameters (WS2 and WS3 tune these; record final values here)
# ---------------------------------------------------------------------------
PARAMS = {
    # S2 change detection
    "logratio_threshold_db": -3.0,   # fallback rule; replaced by the statistical test
    "omnibus_alpha": 0.01,           # false-alarm rate for the sequential omnibus test
    "min_consecutive_dates": 2,      # change must persist on this many dates
    "min_patch_ha": 1.0,             # smallest patch kept
    "reference_drift_db": -1.0,      # HV already this far down across the reference dates: not eligible
    "edge_buffer_km": 5.0,           # patches this close to the swath edge get the "edge" flag
    # S3 hotspot cross-check
    "buffer_km": 1.0,                # hotspot must be within this distance of the patch
    "window_slack_days": 0,          # extra days before the previous acquisition
    "mc_runs": 300,                  # Monte Carlo runs for the headline range
    "mc_buffer_km": (0.5, 2.0),
    "mc_slack_days": (0, 12),
    # Sensor footprints used to jitter hotspot positions (half-width, metres)
    "footprint_half_m": {"VIIRS": 187.5, "MODIS": 500.0},
}

# Labels used across the pipeline and the app. Do not rename without a PR.
HOTSPOT_STATUS = ("recorded", "none", "insufficient_data")
INTERPRETATION = ("fire_supported", "other_disturbance", "unresolved", "not_assessable", "unreviewed")
CONFIDENCE_TIER = ("high", "medium", "low")
PATCH_FLAGS = ("water", "hh_rise", "rain", "edge", "calibration")

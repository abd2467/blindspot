# WS2: Change detection and synthetic burn test (S2)


**Exact dataset links, filters and right/wrong checks:** [`docs/DATASETS.md`](../DATASETS.md). Use only those sources.

**Goal:** find where the land changed, when, and how sure we are; then prove how small a burn the detector can find.
**You own:** `src/blindspot/s2_change/`. **You produce:** `change.nc`, `patches.geojson`, `timeseries.json`, `synthetic_curve.json`.
**Downstream:** WS3 needs `patches.geojson` for the headline by **Gate 2, 14:00**.

Starting code already runs end to end on fixtures:
- `detect.py`: scene normalisation, sequential omnibus test (`omnibus.py`), log-ratio fallback, persistence rule, patches, time series.
- `synthetic.py`: injects burns into real stable pixels and measures detection.

## Steps

1. **Run it on fixtures (10 min).**
   ```bash
   make demo                     # or: python scripts/run_pipeline.py --fixtures
   ```
   Read `detect.py` and `omnibus.py` top to bottom. Compare `data/fixtures/processed/patches.geojson` with `data/fixtures/truth/events.json` (the known fake burns). Expect the burns found, the clearings found too (they are real change), the late flood not found (it is on the last date).

2. **Check the omnibus test (30 min).** Read Canty et al. (2020), section 2. Confirm the formulas in `omnibus.py` docstring (diagonal dual-pol case). Run `pytest tests/test_omnibus.py`: on pure speckle the false-alarm rate must be close to alpha. If you change anything, keep that test passing.

3. **Real data (when `stack.nc` lands, Gate 1).**
   ```bash
   gh release download data-v1 -D data/interim -p stack.nc
   python -m blindspot.s2_change.detect
   python -m blindspot.contracts change && python -m blindspot.contracts patches
   ```
   Look at it: plot `first_change` and overlay `patches.geojson` in QGIS or geopandas. Upload `change.nc` to the release.

4. **Reference period check (20 min).** The reference is the four June/July dates. Plot the median HV of each reference date over a stable area: if one date is already lower (early fire), remove it from `config.REFERENCE_DATES` (ask the lead to merge the config change).

5. **Stable-forest area (20 min).** Draw one polygon of intact forest with no hotspots (QGIS or geojson.io), save as `data/processed/stable_area.geojson`, and change `normalised_logratio` / `normalise_scene` to use its median instead of the scene median. Scene median is fine if most of the scene is unchanged; the polygon is more defensible.

6. **Sensitivity sweep (40 min).** Run detect with `--alpha 0.001, 0.01, 0.05` and `--method logratio --threshold -2/-3/-4/auto`. Record total change area and patch count for each in a table in your PR (and `data/processed/s2_sensitivity.csv`). Pick defaults with WS4 using the west-half RADD agreement (tune west, report east).

7. **Synthetic burn test (30 min run + 15 min read).**
   ```bash
   python -m blindspot.s2_change.synthetic --trials 3
   ```
   Output: detection rate for 1 to 50 ha and 2 to 6 dB drops, and the false-alarm rate. Set `config.PARAMS["min_patch_ha"]` to the smallest size with ≥ 0.8 detection at 3 dB (via a PR to the lead). Give WS6 the curve for a slide.

8. **Flags (20 min).** Check the `water`, `hh_rise`, `calibration` and `rain` flags make sense on real patches. Add `edge` for patches touching the scene edge or NaN areas.

9. **PR.** Code plus small outputs (`data/processed/patches.geojson`, `timeseries.json`, `synthetic_curve.json`). Large `change.nc` goes to the release.

## Fallbacks
- Omnibus misbehaves on real data (everything or nothing flagged): switch to `--method logratio --threshold auto` and tell WS3. Same contract, nothing downstream changes.
- Too many tiny patches: raise `min_patch_ha` or `--smooth 5`.

## Done when
All four outputs pass the contract checks on real data, the sensitivity table and synthetic curve are in the PR, and the method string in `change.nc` says which test and settings were used.

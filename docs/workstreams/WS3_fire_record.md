# WS3: Fire record and the headline number (S3)


**Exact dataset links, filters and right/wrong checks:** [`docs/DATASETS.md`](../DATASETS.md). Use only those sources.

**Goal:** get every VIIRS and MODIS hotspot for the season, decide for each radar-change patch whether the hotspot record saw it, and compute the headline with its range.
**You own:** `src/blindspot/s3_fire/`. **You produce:** `hotspots.geojson`, `crosscheck.csv`, `crosscheck_stats.json`.
**Downstream:** the headline number by **Gate 2, 14:00**.

Starting code: `firms.py` (download + build; download not yet run against the live API) and `crosscheck.py` (runs on fixtures, includes Monte Carlo).

## Steps

1. **MAP_KEY (5 min).** Get a free key at https://firms.modaps.eosdis.nasa.gov/api/map_key/ and put `FIRMS_MAP_KEY=...` in `.env` (copy `.env.example`).

2. **Download the season (start now, runs in background).**
   ```bash
   python -m blindspot.s3_fire.firms download
   ```
   It walks 1 Jun to 10 Nov in 5-day steps for VIIRS SNPP, NOAA-20, NOAA-21 and MODIS, preferring standard processing (`_SP`) and falling back to near-real-time (`_NRT`). Watch the first few calls: if the API rejects the URL or the day range, fix `API` / `STEP_DAYS` in `firms.py` (check https://firms.modaps.eosdis.nasa.gov/api/area/). It writes `data/raw/firms/coverage.json` listing covered days.

3. **Build hotspots (5 min).**
   ```bash
   python -m blindspot.s3_fire.firms build
   python -m blindspot.contracts hotspots
   ```
   Sanity check: count hotspots per month (should peak Aug to Oct), and plot them over the study box. Commit `data/processed/hotspots.geojson` if under ~5 MB.

4. **Understand the matching rule (15 min).** Read the docstring of `crosscheck.py`. Window = previous radar date to first-change date (plus slack). Buffer = 1 km. Every confidence level counts as recorded (keeps the unrecorded share conservative). Run on fixtures: `make demo`.

5. **Run on real patches (after WS2 posts `patches.geojson`).**
   ```bash
   python -m blindspot.s3_fire.crosscheck
   python -m blindspot.contracts crosscheck && python -m blindspot.contracts crosscheck_stats
   ```
   Post the one-line headline in the chat at Gate 2.

6. **Coverage gaps (20 min).** Check `coverage.json`: any days missing in a patch window make it `insufficient_data`. Report how many patches and how much area that excludes; it goes next to the headline.

7. **Monte Carlo (10 min).** Default 300 runs over hotspot jitter (VIIRS ±187.5 m, MODIS ±500 m), buffer 0.5 to 2 km, slack 0 to 12 days. Note the range is one-sided: wider buffers only add matches. Report p05, p50, p95.

8. **Smoke-gap evidence (stretch, 45 min).** For patches with `none`, count VIIRS overpasses in the window with cloud or smoke over the patch (GIBS or the VIIRS cloud mask). This turns "no hotspot recorded" into "no hotspot recorded and the sensor could not see". Add a column `obscured_passes` to `crosscheck.csv` (optional columns are allowed).

9. **West/east split (20 min, with WS2 and WS4).** Add a `--half east|west|all` option that filters patches by centroid longitude (midpoint 112.6° E). Tune on west, report east.

10. **PR.** Code + `hotspots.geojson`, `crosscheck.csv`, `crosscheck_stats.json`. Put the headline sentence in the PR description.

## Fallbacks
- FIRMS API down or slow: use the FIRMS archive download (https://firms.modaps.eosdis.nasa.gov/download/) for the box and season, save CSVs in `data/raw/firms/`, then `build`.
- No time for Monte Carlo on real data: `--runs 50`.

## Done when
Both outputs pass the checks on real data and the headline sentence (with range, eligible area and settings) is posted for WS5 and WS6.

# Data contracts

These file formats are how the six workstreams connect. **If your output matches the contract, your part plugs in, whatever happens inside your code.** Each contract has an automatic check:

```bash
python -m blindspot.contracts <name> [path]   # one file
python -m blindspot.contracts all             # every file that exists
```

Synthetic files that already match every contract are in `data/fixtures/` (make them with `python scripts/make_fixtures.py`). Build against those until the real upstream file exists.

## Shared rules

- **Grid:** EPSG:32749 (UTM 49S), 60 m pixels, north-up, bounds `(652860, 9654360, 702840, 9704340)`, shape 833 × 833. Defined once in `src/blindspot/config.py`. Fixtures use a 240 × 240 corner of the same grid.
- **Vectors** handed between workstreams are GeoJSON in **EPSG:4326** (lon, lat).
- **Dates** are strings `YYYY-MM-DD`. Radar dates are the 11 in `config.ACQ_DATES`.
- **IDs:** patches are `P0001`, `P0002`, … assigned by S2. Every table about patches is keyed by `patch_id`.
- **One writer per file.** Nobody edits a file another workstream produces. Add your information in your own file, keyed by `patch_id`; S5 merges.
- **Units:** backscatter is linear power in the stack, dB everywhere else (named `*_db`). Areas in ha (patches) or km² (stats).

## Files

### `data/interim/stack.nc`: WS1 → WS2, WS4, S5
NetCDF (xarray).

| Variable | Dims | Type | Meaning |
|---|---|---|---|
| `hh`, `hv` | time, y, x | float32 | Linear backscatter power (γ⁰ or σ⁰, state which in `attrs['notes']`). NaN = invalid |
| `water` | y, x | uint8 | 1 = permanent water |
| coord `processing_version` | time | str | e.g. `P05023` |

Attributes: `crs="EPSG:32749"`, `enl` (looks per 60 m pixel, 0 if unknown), `track`, `frame`, `fixture` (1 for synthetic), `notes`.

### `data/interim/change.nc`: WS2 → WS4, S5
Variables on (y, x): `changed` uint8, `first_change` int16 (index into the dates, -1 = none), `n_changed` int16, `min_logratio_db` float32, `p_value` float32. Attribute `method` describes the test and its settings.

### `data/processed/patches.geojson`: WS2 → WS3, WS4, S5
Polygons in EPSG:4326. Properties:

| Property | Type | Meaning |
|---|---|---|
| `patch_id` | str | `P0001` … |
| `area_ha` | float | Patch area |
| `first_change_date` | date | First radar date showing the change |
| `prev_acq_date` | date | Radar date before it (start of the fire-matching window) |
| `n_dates_changed` | int | Dates with HV ≥ 1 dB below reference |
| `mean_drop_hv_db` | float | Mean HV log-ratio after the change (negative = drop) |
| `hh_change_db` | float | Mean HH change after vs before |
| `flags` | list[str] | Any of `water`, `hh_rise`, `rain`, `edge`, `calibration` |

### `data/processed/timeseries.json`: WS2 → S5, web
```json
{"dates": ["2026-06-18", ...],
 "patches": {"P0001": {"hv_db": [...], "hh_db": [...]}},
 "reference": {"hv_db": [...], "hh_db": [...]}}
```
One value per date. `reference` is the median over stable (unchanged, non-water) pixels.

### `data/processed/synthetic_curve.json`: WS2 → WS4, S5
`{"method", "injected_date", "curve": [{"drop_db", "size_ha", "trials", "detection_rate"}], "false_alarm_rate", "note"}`

### `data/processed/hotspots.geojson`: WS3 → S5
Points in EPSG:4326. Properties: `sensor` (`VIIRS` or `MODIS`), `satellite`, `acq_date`, `acq_time` (HHMM UTC), `confidence`, `frp`, `source` (`SP` or `NRT`).
Plus `data/raw/firms/coverage.json`: `{source: [dates covered]}`.

### `data/processed/crosscheck.csv`: WS3 → WS4, S5
Columns: `patch_id, hotspot_status, n_hotspots, nearest_hotspot_km, window_start, window_end`. `hotspot_status` ∈ `recorded`, `none`, `insufficient_data`.

### `data/processed/crosscheck_stats.json`: WS3 → S5
```json
{"total_change_km2", "no_hotspot_km2", "no_hotspot_share",
 "n_patches", "n_recorded", "n_none", "n_insufficient",
 "mc": {"p05", "p50", "p95", "runs"},
 "params": {...},
 "by_date": [{"date", "change_km2", "no_hotspot_km2", "n_hotspots"}]}
```

### `data/processed/review.csv`: WS4 → S5
Columns: `patch_id, confidence_tier, interpretation, radd_agree, notes, evidence_urls`.
`confidence_tier` ∈ `high, medium, low`. `interpretation` ∈ `fire_supported, other_disturbance, unresolved, not_assessable, unreviewed`. `radd_agree` is `true`, `false` or empty.

### `data/processed/reference_sample.csv`: WS4 (internal)
Columns: `point_id, stratum, lon, lat, label, labeller, notes`. `stratum` ∈ `change_hotspot, change_no_hotspot, no_change`. `label` ∈ `burn, clearing, flood, no_change, unclear`. With `strata_pixel_counts.json`.

### `data/processed/validation_stats.json`: WS4 → S5
`{"radd_agreement": {"share", "n_patches"} | null, "sample": {"n", "n_labelled"} | null, "area_estimate": {"km2", "ci95_low", "ci95_high", "n_used", "target_labels"} | null, "synthetic": <synthetic_curve.json> | null}`

### `data/processed/rain_daily.csv`: WS4 → S5
Columns: `date, precip_mm` (area mean over the study box).

### `data/processed/peat_mask.tif`: WS4 → S5 (optional)
uint8 GeoTIFF on the analysis grid: 1 = peat-dominated, 2 = peat in soil mosaic, 0 = other.

### `data/processed/psi_daily.csv`: WS6 → S5
Columns: `date, psi_24h_max, region`.

### `data/processed/eonet_events.geojson`: WS6 → S5
Points with properties `id, title, date, source`.

### `web/data/`: S5 → WS5
Written only by `python -m blindspot.s5_package.package`.

| File | Content |
|---|---|
| `manifest.json` | `fixture`, `generated`, `study_bbox`, `bounds` (Leaflet `[[s,w],[n,e]]`), `dates`, `processing_version`, `overlays` (`{date: "overlays/hv_DATE.png"}`), `display_db_range`. Optional: `inputs` (`{stack, patches, timeseries, hotspots, crosscheck, review, validation, psi, rain, events, peat}`: true when that input existed at packaging), `peat` (`{url, bounds}`). Without `stack.nc`, `dates` come from `config.ACQ_DATES`, `bounds` from the study box and `overlays` is `{}` |
| `overlays/hv_YYYY-MM-DD.png` | HV in dB, stretched -20 to -5 dB, RGBA, EPSG:4326 |
| `overlays/peat.png` (optional) | WS4's `peat_mask.tif` as a translucent brown overlay |
| `patches.geojson` | patches + `hotspot_status` (`unknown` until WS3 delivers), `n_hotspots`, `nearest_hotspot_km`, `confidence_tier` (`unrated` until WS4 delivers), `interpretation`, `notes`. Optional: `window_start`, `window_end` (from `crosscheck.csv`), `radd_agree` (true, false or null), `evidence_urls` (list) |
| `hotspots.geojson` | points with `sensor, acq_date, confidence, frp` |
| `timeseries.json` | as above |
| `stats.json` | `{"crosscheck": <crosscheck_stats>, "validation": <validation_stats>}` |
| `psi.json`, `rain.json` | `[{"date", "value"}]` |
| `events.geojson` | EONET points |

## Changing a contract

1. Open an issue titled `contract: <file>` saying what changes and why.
2. The integration lead and every workstream that reads the file agree in the issue.
3. One PR changes, together: this document, `src/blindspot/contracts.py`, `scripts/make_fixtures.py` if needed, and the producer's code. CI must pass on fixtures.
4. Announce it in the team chat. Readers update their code in their own PRs.

Adding a new optional property or column is not a breaking change: just document it here.

# WS4: Validation and evidence (S4)


**Exact dataset links, filters and right/wrong checks:** [`docs/DATASETS.md`](../DATASETS.md). Use only those sources.

**Goal:** show how far the result can be trusted, and give each important patch an interpretation backed by independent evidence.
**You own:** `src/blindspot/s4_validate/`. **You produce:** `review.csv`, `reference_sample.csv`, `validation_stats.json`, `rain_daily.csv`, `peat_mask.tif`, `radd_by_patch.json`.

Starting code: `validate.py` with `sample`, `review`, `radd` and `stats` commands. All run on fixtures (`make demo`), where the sample is auto-labelled from synthetic truth. On real data **you** label it.

## Steps

1. **Accounts (10 min).** Google Earth Engine (https://code.earthengine.google.com, register a noncommercial project) and an Earthdata login (for GPM IMERG).

2. **RADD export (start early, 30 min).** In the Earth Engine Code Editor, run:
   ```javascript
   // RADD forest disturbance alerts for the Blindspot study box. Check the asset id on the RADD page.
   var box = ee.Geometry.Rectangle([112.375, -3.125, 112.825, -2.675]);
   var radd = ee.ImageCollection('projects/radar-wur/raddalert/v1')
       .filterMetadata('layer', 'contains', 'alert')
       .filterMetadata('geography', 'equals', 'asia')
       .sort('system:time_end', false).first();
   // 'Date' band: alert date encoded as YYDOY (check the dataset description and convert if needed)
   Export.image.toDrive({image: radd.select('Date').toInt32(), description: 'radd_alerts',
     region: box, crs: 'EPSG:32749', crsTransform: [60, 0, 652860, 0, -60, 9704340],
     maxPixels: 1e9});
   ```
   Read the RADD dataset description and confirm the date encoding. `validate.py radd` expects **days since 2014-12-31**: convert in Earth Engine or in Python before saving to `data/raw/radd_alerts.tif`. Check the licence on the RADD page and add it to `docs/DATA_REGISTER.md`.

3. **Peat map (20 min).** Download Global Peatland Map 2.0 (link on https://gee-community-catalog.org/projects/peatland/, also in Earth Engine community catalog). Reproject to the grid (nearest neighbour) and save `data/processed/peat_mask.tif`:
   ```python
   import rasterio, numpy as np
   from rasterio.warp import reproject, Resampling
   from blindspot import config as C
   from blindspot.grid import coords, transform_from_coords
   x, y = coords(); dst = np.zeros(C.GRID_SHAPE, "uint8")
   with rasterio.open("data/raw/peatland_map.tif") as s:
       reproject(rasterio.band(s, 1), dst, dst_transform=transform_from_coords(x, y), dst_crs=C.CRS, resampling=Resampling.nearest)
   with rasterio.open("data/processed/peat_mask.tif", "w", driver="GTiff", height=dst.shape[0], width=dst.shape[1],
                      count=1, dtype="uint8", crs=C.CRS, transform=transform_from_coords(x, y)) as o: o.write(dst, 1)
   ```
   In the brief and app: peat overlap shows fire **on mapped peat**, not that the peat itself burned.

4. **Rainfall (30 min).** Area-mean daily precipitation over the box, 1 Jun to 10 Nov 2026, from NASA GPM IMERG Late run daily (`GPM_3IMERGDL`; the Final run lags by months). Easiest: NASA Giovanni "Area-Averaged Time Series" → CSV. Save as `data/processed/rain_daily.csv` with columns `date, precip_mm`. Check: `python -m blindspot.contracts rain`.

5. **RADD agreement (10 min, after WS2's patches).**
   ```bash
   python -m blindspot.s4_validate.validate radd
   ```
   A patch agrees if ≥ 30% of it has a RADD alert dated from 30 days before its window to 12 days after.

6. **Review table (5 min).** `python -m blindspot.s4_validate.validate review` creates `review.csv` with rule-based confidence tiers. Rerun after RADD; your manual edits to `interpretation` and `notes` are kept.

7. **Review 10 or more patches (90 min, the most valuable hour).** Pick: the 3 largest `none` patches, 3 largest `recorded`, 2 flagged, 2 random. For each, look at:
   - HLS / Sentinel-2 before and after (Copernicus Browser or NASA Worldview): burn scar (dark, brown), clearing (straight edges, bare soil), flooding (water)?
   - RADD alert and its date.
   - Hotspots nearby in time (from `hotspots.geojson`).
   - Rain around the change date (`rain_daily.csv`).
   Set `interpretation` (fire_supported, other_disturbance, unresolved, not_assessable) and write one line of `notes` with the evidence, plus links in `evidence_urls`. Screenshot two clear examples for WS6.

8. **Reference sample (60 min labelling).**
   ```bash
   python -m blindspot.s4_validate.validate sample
   ```
   Label all ~50 points in `reference_sample.csv`: `burn`, `clearing`, `flood`, `no_change`, `unclear`. Label from imagery only, without looking at the stratum column first if you can (less bias). Two people labelling and comparing is better than one.

9. **Stats (5 min).** `python -m blindspot.s4_validate.validate stats` → `validation_stats.json` with RADD agreement, Olofsson area and 95% CI, and the synthetic curve from WS2.

10. **PR** with all outputs (small files) and a short paragraph: "RADD agrees on X%; error-adjusted area Y km² (95% CI a to b); of 10 reviewed patches, n fire-supported, n other, n unresolved."

## Fallbacks
- No Earth Engine: skip RADD, rely on the reviewed patches and the labelled sample; say so in the app.
- Not enough time to label 50: label at least 10 per stratum; the CI widens and that is honest.

## Done when
`review.csv` and `validation_stats.json` pass the checks, at least 10 patches have a reviewed interpretation, and every source you used is in `docs/DATA_REGISTER.md`.

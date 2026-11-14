# Datasets: exact links, exact filters, and how to know you got the right one

Use **only** these sources, with these exact IDs and filters. If something here doesn't match what you see, stop and post in the team chat before you continue: wrong data costs more time than waiting.

Shared settings (also in `src/blindspot/config.py`):
- **Study box (WGS84):** west 112.375, south -3.125, east 112.825, north -2.675
- **Season:** 2026-06-01 to 2026-11-10
- **Radar dates:** 2026-06-18, 06-30, 07-12, 07-24, 08-17, 08-29, 09-10, 09-22, 10-04, 10-16, 10-28 (early August is missing in the archive: that is expected)

---

## WS1: NISAR radar

| Item | Exact value | Link |
|---|---|---|
| Collection, 18 Jun to 16 Oct | `NISAR_L2_GCOV_PROVISIONAL_V1` (CMR id `C2854338529-ASF`) | [CMR record](https://cmr.earthdata.nasa.gov/search/collections.json?short_name=NISAR_L2_GCOV_PROVISIONAL_V1) · [Earthdata Search](https://search.earthdata.nasa.gov/search?q=NISAR_L2_GCOV_PROVISIONAL_V1) |
| Collection, 28 Oct | `NISAR_L2_GCOV_V1` (CMR id `C3622241360-ASF`) | [CMR record](https://cmr.earthdata.nasa.gov/search/collections.json?short_name=NISAR_L2_GCOV_V1) · [Earthdata Search](https://search.earthdata.nasa.gov/search?q=NISAR_L2_GCOV_V1) |
| Granules for our box | CMR granule search | [Provisional granules over the box](https://cmr.earthdata.nasa.gov/search/granules.json?short_name=NISAR_L2_GCOV_PROVISIONAL_V1&bounding_box=112.375,-3.125,112.825,-2.675&page_size=100) · [Validated granules](https://cmr.earthdata.nasa.gov/search/granules.json?short_name=NISAR_L2_GCOV_V1&bounding_box=112.375,-3.125,112.825,-2.675&page_size=100) |
| Filter | name contains **`4005_DHDH`** (dual-pol HH+HV), track **061**, **descending**, frame **090** | |
| Backup track | ascending track 125, frame 176 (10 dates) | |
| Water mask / DEM | `NISAR_WATERMASK`, `NISAR_DEM` | [Earthdata Search](https://search.earthdata.nasa.gov/search?q=NISAR_WATERMASK) |
| Docs | NISAR Data User Guide; ASF NISAR cookbook notebooks (challenge resources) | [User Guide](https://nisar-docs.asf.alaska.edu/) · [ASF Vertex](https://search.asf.alaska.edu/) |
| Login | Earthdata | [register](https://urs.earthdata.nasa.gov/users/new) |

**You have the right data if:** 11 granules, one per date above, all `4005_DHDH`, all the same track and frame; 10 with processing `P05023`, the 28 Oct one `P05036`. Linear HV over forest ≈ 0.04 to 0.08 (≈ -14 to -11 dB); rivers below -20 dB.
**Wrong data traps:** `SHSH` granules (single-pol, no HV: unusable); a different track or frame (different geometry: never mix); values already in dB; the whole 5 GB file downloaded instead of the window.

## WS2: no external data
Inputs come only from WS1 (`stack.nc`). Test on `data/fixtures`. Do not download anything.

## WS3: fire record

| Item | Exact value | Link |
|---|---|---|
| API key | free FIRMS MAP_KEY | [get a key](https://firms.modaps.eosdis.nasa.gov/api/map_key/) |
| API | area API, CSV | [API docs](https://firms.modaps.eosdis.nasa.gov/api/area/) |
| Sources (in this order) | `VIIRS_SNPP_SP` → fallback `VIIRS_SNPP_NRT`; `VIIRS_NOAA20_SP` → `VIIRS_NOAA20_NRT`; `VIIRS_NOAA21_NRT`; `MODIS_SP` → `MODIS_NRT` | |
| Area string | `112.325,-3.175,112.875,-2.625` (box + 0.05° margin, what `firms.py` sends) | |
| Backup (if the API fails) | FIRMS archive download for the same box and season, CSV | [archive download](https://firms.modaps.eosdis.nasa.gov/download/) |

**You have the right data if:** VIIRS rows have `bright_ti4`, MODIS rows have `brightness`; dates fall inside 1 Jun to 10 Nov 2026; counts peak in Aug to Oct; every point lies inside the box + margin; `coverage.json` lists most days.
**Wrong data traps:** only one VIIRS satellite (we need SNPP, NOAA-20, NOAA-21 and MODIS); a filter on confidence (we count every confidence level); a country-wide file not clipped; duplicate rows from overlapping NRT and SP pulls (`build` de-duplicates).

## WS4: validation and evidence

| Item | Exact value | Link |
|---|---|---|
| RADD alerts | Earth Engine asset `projects/radar-wur/raddalert/v1`, geography `asia`, latest alert image, band `Date` | [RADD page](https://www.wur.nl/en/research/products-services/radd-forest-disturbance-alert) · [Earth Engine Code Editor](https://code.earthengine.google.com) |
| Rainfall | GPM IMERG **Late** run daily, `GPM_3IMERGDL` version 07 (the Final run is months behind) | [GES DISC dataset](https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGDL_07/summary) · [Giovanni area-average time series](https://giovanni.gsfc.nasa.gov/giovanni/) |
| Peat map | Global Peatland Map 2.0 (Greifswald Mire Centre), 1 km GeoTIFF: 1 = peat-dominated, 2 = peat in soil mosaic | [catalog page with download link](https://gee-community-catalog.org/projects/peatland/) |
| Optical checks | HLS (`HLSS30`, `HLSL30`) or Sentinel-2 L2A, cloud-free days only | [HLS in Earthdata Search](https://search.earthdata.nasa.gov/search?q=HLSS30) · [NASA Worldview](https://worldview.earthdata.nasa.gov) · [Copernicus Browser](https://browser.dataspace.copernicus.eu) |
| Soil moisture (optional) | `NISAR_L3_SME2_PROVISIONAL_V1` | [CMR record](https://cmr.earthdata.nasa.gov/search/collections.json?short_name=NISAR_L3_SME2_PROVISIONAL_V1) |

**You have the right data if:** the RADD export is on our grid (EPSG:32749, 60 m, origin 652860 / 9704340) and its dates convert to 2026 for recent alerts; rainfall rises sharply from late October; the peat raster has values 0, 1, 2 only.
**Wrong data traps:** RADD date encoding (read the dataset description; `validate.py radd` expects days since 2014-12-31); IMERG Final instead of Late (no data for Oct 2026); any Indonesian government peat or concession map (**not allowed**, see the brief).

## WS5: live services in the app

| Item | Exact value | Link |
|---|---|---|
| GIBS true colour | WMS `https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi`, layer `VIIRS_SNPP_CorrectedReflectance_TrueColor` (backup `MODIS_Terra_CorrectedReflectance_TrueColor`), WMS 1.3.0, EPSG:4326 | [GIBS docs](https://nasa-gibs.github.io/gibs-api-docs/) |
| Base map | OpenStreetMap tiles, attribution required | [tile policy](https://operations.osmfoundation.org/policies/tiles/) |
| Libraries | Leaflet 1.9.4, Chart.js 4.4.1, bundled in `web/vendor/` so the demo works offline | |

Everything else the app shows comes from `web/data/`. Never fetch other data in the browser.

## WS6: context

| Item | Exact value | Link |
|---|---|---|
| Singapore PSI, per day | `https://api-open.data.gov.sg/v2/real-time/api/psi?date=YYYY-MM-DD`, field `readings.psi_twenty_four_hourly` | [example: 9 Oct 2026](https://api-open.data.gov.sg/v2/real-time/api/psi?date=2026-10-09) |
| Singapore PSI, history CSV | Apr 2014 to Sep 2026, hourly, 5 regions | [data.gov.sg dataset](https://data.gov.sg/datasets/d_b4cf557f8750260d229c49fd768e11ed/view) |
| EONET wildfires | category `wildfires`, status `all`, 2026-06-01 to 2026-11-10, bbox `108,1,117,-5` | [exact query](https://eonet.gsfc.nasa.gov/api/v3/events?category=wildfires&status=all&start=2026-06-01&end=2026-11-10&bbox=108,1,117,-5) |
| Challenge page | Dancing with the SARs | [details and resources](https://www.spaceappschallenge.org/2026/challenges/dancing-with-the-sars/?tab=details) |

**You have the right data if:** PSI crosses 100 on 4 Sep 2026 and reaches 192 on 9 Oct 2026; EONET returns dozens of wildfire events in the box, with a cluster near 112.6° E, 2.9° S.
**Wrong data traps:** 1-hour PM2.5 or 3-hour PSI instead of the 24-hour PSI; a single region instead of the daily maximum across regions.

---

## Final check before you hand off any file

```bash
python -m blindspot.contracts <name> <path>
```
If it passes, your file plugs into everyone else's work. If it fails, fix the file and don't change the check. If the check itself is wrong, tell the lead.

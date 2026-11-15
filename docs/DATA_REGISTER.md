# Data register

Every external dataset, API, image and library we use. This feeds the Space Apps **References** field. Whoever adds a source fills its row, including the licence (check the provider's page; write "to check" if unsure) and the date downloaded.

| Source | Provider | Used for | Workstream | Licence / terms | Link | Downloaded |
|---|---|---|---|---|---|---|
| NISAR L2 GCOV Provisional (`NISAR_L2_GCOV_PROVISIONAL_V1`) | NASA / ASF DAAC | Radar backscatter, 18 Jun to 16 Oct 2026 | WS1 | NASA open data policy | https://search.earthdata.nasa.gov | |
| NISAR L2 GCOV (`NISAR_L2_GCOV_V1`) | NASA / ASF DAAC | Radar backscatter, 28 Oct 2026 | WS1 | NASA open data policy | https://search.earthdata.nasa.gov | |
| NISAR water mask / DEM | NASA / ASF DAAC | Water masking | WS1 | NASA open data policy | https://search.earthdata.nasa.gov | |
| NISAR L3 Soil Moisture (`NISAR_L3_SME2_PROVISIONAL_V1`) | NASA / ASF DAAC | Context | WS4 | NASA open data policy | https://search.earthdata.nasa.gov | |
| FIRMS VIIRS 375 m and MODIS active fire | NASA LANCE / FIRMS | Hotspot record | WS3 | NASA open data policy | https://firms.modaps.eosdis.nasa.gov/api/area/ | |
| GPM IMERG Late daily (`GPM_3IMERGDL`) | NASA GES DISC | Rainfall | WS4 | NASA open data policy | https://disc.gsfc.nasa.gov (via Giovanni area-averaged time series) | 2026-11-15 |
| EONET wildfire events | NASA | Story markers | WS6 | NASA open data policy | https://eonet.gsfc.nasa.gov/api/v3/events | |
| GIBS corrected reflectance | NASA | "Why radar" imagery | WS5 | NASA open data policy | https://gibs.earthdata.nasa.gov | live |
| RADD forest disturbance alerts | Wageningen University & Research | Validation | WS4 | CC BY 4.0 (as stated on the Earth Engine community catalog page, https://gee-community-catalog.org/projects/radd/) | https://www.wur.nl/en/research/products-services/radd-forest-disturbance-alert | 2026-11-15 |
| HLS / Sentinel-2 | NASA / ESA Copernicus | Optical spot-checks | WS4 | open (Copernicus terms) | https://www.earthdata.nasa.gov/data/projects/hls | |
| Global Peatland Map 2.0 (`GPM2022_GMC.zip`, 1 km, 2 classes) | Greifswald Mire Centre / UNEP | Peat context | WS4 | CC BY-NC-SA 4.0 (licence file in the download; derived `peat_mask.tif` carries the same terms) | https://gee-community-catalog.org/projects/peatland/ | 2026-11-15 |
| Historical 24-hr PSI | NEA via data.gov.sg | Singapore timeline | WS6 | Singapore Open Data Licence | https://data.gov.sg/datasets/d_b4cf557f8750260d229c49fd768e11ed/view | |
| OpenStreetMap tiles | OpenStreetMap contributors | Not used since the WS5 redesign (no base map); keep the row if a base map returns | WS5 | ODbL, attribution required | https://www.openstreetmap.org/copyright | |
| Leaflet, Chart.js | open source | Web app | WS5 | BSD-2 / MIT | https://leafletjs.com, https://www.chartjs.org | |
| KaTeX 0.16.47 (js, css, woff2 fonts) | open source | Method page formulas (`web/vendor/katex/`) | WS5 | MIT | https://katex.org | 2026-11-15 |
| Blue Marble (day) and Black Marble (night) Earth textures, plus a water mask | NASA Visible Earth, via the `three-globe` example images | Globe on the start screen (`web/assets/globe/`) | WS5 | NASA imagery: public domain; three-globe: MIT. Exact source images to check | https://visibleearth.nasa.gov/collection/1484/blue-marble | 2026-11-14 |
| Space Grotesk, Inter, JetBrains Mono (woff2) | Florian Karsten; Rasmus Andersson; JetBrains, via Fontsource | Web app type (`web/vendor/fonts/`) | WS5 | SIL Open Font License 1.1 | https://fontsource.org | 2026-11-14 |

**Not used, on purpose:** concession or ownership maps, and any data from Indonesian government platforms (see `docs/BRIEF.md`, Risks).

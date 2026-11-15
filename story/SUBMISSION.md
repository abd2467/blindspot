# Submission text (paste into Team Page → Project → Edit, then click "Submit for Judging")

## 1. Project name

BlindSpot: What the hotspots missed

## Summary

Indonesia's fire record comes from heat-sensing satellites (MODIS, VIIRS), and smoke, cloud and smouldering peat can hide fires from them. BlindSpot uses NASA-ISRO NISAR L-band radar, which sees through smoke, to map land change across a 50 × 50 km peat landscape near Sampit, Central Kalimantan, over the 2026 fire season, and checks every change patch against NASA FIRMS hotspots. Result: 71% of radar-detected change had no fire hotspot recorded (range 61 to 75%), most of it early in the season: 82% from late August to September, 23% in October. A place to look, every 12 days.

## 2. Project demo (7 slides)

https://github.com/abd2467/blindspot/blob/main/story/BlindSpot_slides.pdf

## 3. Final project link

Live app: https://blindspotsg.earth
Code: https://github.com/abd2467/blindspot

## 4. Detailed project description

**How it works.** (1) We stream the study window of 11 NISAR L2 GCOV images (18 Jun to 28 Oct 2026, track 061, frame 090, HH and HV) onto a 60 m grid. (2) Each date is normalised by its scene-wide ratio to the June to July reference, which cancels rain, soil moisture and calibration shifts. (3) A sequential omnibus test (Conradsen et al. 2016; Canty et al. 2020) at a 1% false-alarm rate, with effective looks measured from the reference dates, finds the first date each pixel changed; HV must stay at least 1 dB down for two dates, and patches of 1 ha or more are kept. Pixels already drying within the reference, water and the radar's swath edge are handled explicitly. (4) A patch counts as "recorded" if a VIIRS or MODIS hotspot lies within 1 km of it between the previous radar date and the change date. (5) The headline is the area share of change with no hotspot recorded, with a 300-run Monte Carlo range (hotspot position, 0.5 to 2 km buffer, 0 to 12 days slack).

**Validation.** Synthetic burns injected into the real radar (about 3 ha and up detected every time at 4 dB or more; 0.006% false alarms), a 48-point labelled stratified sample with an Olofsson (2014) error-adjusted area (221 km², 95% CI 0 to 496 km²), 10 patches reviewed by hand (3 fire supported, 6 other disturbance, 1 unresolved), and agreement with RADD radar alerts (0.2% of patches). We report the 17 Aug pass, the first after a 24-day acquisition gap, separately: without it the share is 59%.

**Key features.** Interactive map with an 11-date timeline, before and after views, per-patch radar history and evidence, a "Why radar" explainer with real NASA imagery of the smoke, a Singapore haze section, and a Method page with every formula and a table of uncertainty sources.

**Benefits.** A screening tool for analysts, journalists and peat agencies: it shows where land changed under the smoke and what the hotspot record says, especially early in the fire season. It never claims who caused a change or that a patch is a missed fire: "no hotspot recorded" is a place to look.

**Technologies.** Python (numpy, xarray, rasterio, geopandas, shapely, scipy), earthaccess and h5py for streaming NISAR, a statistical test with no machine learning, a static web app (Leaflet, Chart.js, KaTeX, WebGL globe) on GitHub Pages, and GitHub Actions to package outputs and deploy.

## 5. NASA and space agency partner data

- **NISAR L2 GCOV** (NASA-ISRO, ASF DAAC): `NISAR_L2_GCOV_PROVISIONAL_V1`, `NISAR_L2_GCOV_V1`, 11 dates. The radar backscatter all change detection is built on.
- **FIRMS VIIRS (Suomi NPP, NOAA-20, NOAA-21) and MODIS (Terra, Aqua) active fires** (NASA LANCE/FIRMS): 38,831 hotspots, the fire record we audit.
- **GPM IMERG** (NASA GES DISC): daily rain, used to flag rain-affected change.
- **GIBS / Worldview VIIRS corrected reflectance** (NASA): the smoke image of the study area on 22 Sep 2026 and the "Why radar" imagery.
- **Blue Marble and Black Marble** (NASA Visible Earth): the globe on the start screen.

## 6. References

Data: NISAR L2 GCOV (NASA-ISRO, ASF DAAC); NASA FIRMS VIIRS and MODIS active fires; GPM IMERG (NASA GES DISC); NASA GIBS and Worldview; NASA Blue Marble and Black Marble; RADD forest disturbance alerts (Wageningen University, CC BY 4.0); Singapore PSI (NEA, data.gov.sg).
Methods: Conradsen et al. (2016) IEEE TGRS, omnibus test for change in polarimetric SAR; Canty, Nielsen, Conradsen and Skriver (2020) Remote Sensing, sequential omnibus change detection; Olofsson et al. (2014) Remote Sensing of Environment, good practices for area estimation and accuracy assessment.
Evidence for the problem: Sofiev and Kouznetsov (2026) Geoscientific Model Development; NASA Earth Observatory (Sep 2026); NEA haze updates (Sep to Oct 2026).
Software: Python scientific stack, Leaflet, Chart.js, KaTeX, Space Grotesk, Inter and JetBrains Mono fonts.
AI tools: Claude (Anthropic) assisted with code, data checks, the web app and writing. [Add any other AI tools teammates used.]
Full lists: `story/references.md` and `docs/DATA_REGISTER.md` in the repo.

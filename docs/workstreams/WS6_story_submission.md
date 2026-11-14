# WS6: Story, context data and submission


**Exact dataset links, filters and right/wrong checks:** [`docs/DATASETS.md`](../DATASETS.md). Use only those sources.

**Goal:** make judges understand the problem, the idea and the result in 30 seconds (video) or 7 slides, and get the submission in on time with every reference listed.
**You own:** `src/blindspot/s6_context/`, `story/`. **You produce:** `psi_daily.csv`, `eonet_events.geojson`, the slides or video, the References text, the final submission.

Presentation is a fifth of the score. The judging guide says teams often neglect it. Don't.

## Steps

1. **Context data (30 min, start now).**
   ```bash
   python -m blindspot.s6_context.context eonet
   python -m blindspot.s6_context.context psi
   python -m blindspot.contracts events && python -m blindspot.contracts psi
   ```
   If the PSI API refuses requests, download the historical CSV from data.gov.sg (link in `docs/BRIEF.md` section 12) and fill Oct to Nov with the API. Check that 9 Oct 2026 shows the 192 peak.

2. **Choose the format (5 min, with the lead).** 30-second video or 7 slides, not both. Recommendation: video, if WS5's app plays well, because it shows the product working.

3. **Script (45 min).** Use `story/script.md`. Three acts:
   - **Dry:** June to August, the landscape and the radar baseline.
   - **Fire:** September and October, smoke hides the land in optical; NISAR shows patches appearing; hotspots light up some and not others.
   - **Rain:** late October, the wet season returns; the headline number.
   Every number must come from `web/data/stats.json` or `docs/BRIEF.md`. No "missed fires": say "change with no hotspot recorded".

4. **Visuals (60 min).**
   - GIBS true colour on 9 Oct (grey smoke) vs NISAR the same week: grab from the app's Why radar panel.
   - The timeline playing (screen recording of the deployed app).
   - The synthetic burn curve from WS2 (one simple chart).
   - Two reviewed patches from WS4 (before/after optical, radar history).

5. **Slides (if slides) (90 min).** Max 7 including title: 1 title and one-line pitch; 2 problem with evidence (PSI 192, hotspots go blind); 3 idea (radar audits the hotspot record); 4 method in one diagram; 5 result (headline + range + map); 6 validation and honesty (synthetic test, RADD, CI, two-label system); 7 impact and next steps (more tracks, near-real-time with NISAR's 12-day revisit).

6. **Video (if video) (90 min).** 30 s max, English, subtitles burned in. Record the deployed app, not localhost. Export 1080p. Keep the headline on screen for at least 4 seconds.

7. **References (30 min).** Build the References field from `docs/DATA_REGISTER.md` and `docs/BRIEF.md` section 12: every dataset, library (Leaflet, Chart.js, xarray, rasterio, geopandas, earthaccess, scipy), paper, and image.

8. **Submit (by 23:00).** On the Space Apps team page → Project tab: title "Blindspot", short description (use the README tagline), the demo, the repo link, the deployed URL, References. Press submit. Check it shows as **submitted**. Screenshot it and post in the chat.

9. **Judge Q&A sheet (30 min).** One page in `story/qa.md`: "Is this proof of illegal burning?", "Why not just use RADD?", "How do you know it's fire and not clearing?", "What about rain?", "Why only one track?", "What would it take to scale?". Answers are in `docs/BRIEF.md` sections 5, 6, 10.

## Hand-off (required: integration cannot use anything left on your machine)
By **19:00 SGT**:
- **Merged into `main`:** code, `psi_daily.csv`, `eonet_events.geojson` (in `data/processed/`), everything in `story/`.
- **Uploaded to release `data-v1`:** the video file, if any.
- Contract check output pasted in the PR; file names posted in the team chat.
The integrator has none of your logins, so it cannot rerun your downloads. If you will miss this, say so in the chat before the deadline and name your fallback.

## Done when
The submission shows as submitted before 23:00, with the demo, repo link, live URL and full References.

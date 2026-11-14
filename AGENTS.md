# AGENTS.md: context for any AI assistant working on Blindspot

This file briefs any AI coding assistant or chatbot (Claude, ChatGPT, Codex, Cursor, Copilot, Gemini). Claude Code reads `CLAUDE.md`, which points here; Codex, Cursor and others read this file directly. **If you use a chat assistant without repo access, paste this whole file at the start of the chat, then paste your workstream guide from `docs/workstreams/`.**

## 1. The project in one paragraph

**Blindspot: what the hotspots missed.** A NASA Space Apps 2026 entry (Singapore local event, challenge "Dancing with the SARs"; deadline Sun 15 Nov 2026, 23:59 SGT). Smoke and cloud hide Indonesia's peatland fires from the MODIS and VIIRS fire satellites, so the hotspot record is least complete when haze is worst. NISAR's L-band radar sees through smoke. We map land change in a 50 × 50 km peat landscape near Sampit, Central Kalimantan, from 11 NISAR GCOV dates (18 Jun to 28 Oct 2026, track 061 descending, frame 090), check each change patch against NASA FIRMS hotspots, and report **the share of radar-detected change with no hotspot recorded**, with an uncertainty range, in a static web app. Full brief: `docs/BRIEF.md`.

## 2. Method (keep to this)

1. S1: stream the study window of each GCOV granule (HH, HV linear power), average onto a 60 m grid in EPSG:32749.
2. S2: per-date scene normalisation; **sequential omnibus test** (Conradsen 2016, dual-pol form per Canty 2020) at alpha 0.01 with effective looks measured from the reference dates; HV must stay ≥ 1 dB below reference for 2 dates; patches ≥ 1 ha; flags. Fallback: HV log-ratio threshold.
3. S3: patch is `recorded` if a VIIRS/MODIS hotspot is within 1 km and dated between the previous radar date and the change date; else `none`, or `insufficient_data` if fire data is missing. Headline = unrecorded share of change area; Monte Carlo range (hotspot jitter, buffer 0.5 to 2 km, slack 0 to 12 days).
4. S4: RADD agreement, stratified reference sample labelled from optical imagery, Olofsson (2014) error-adjusted area with 95% CI, per-patch confidence tier and reviewed interpretation.
5. Simulation: synthetic burn test (injected 1 to 50 ha, 2 to 6 dB drops in real stable pixels) and the Monte Carlo above.

The method is statistical and physics-based. Do not introduce trained or learned models, and do not suggest them.

## 3. Repository map

```
src/blindspot/config.py      shared grid, dates, paths, parameters (lead owns)
src/blindspot/contracts.py   checks for every hand-off file (lead owns)
src/blindspot/grid.py        grid helpers
src/blindspot/s1_ingest/     WS1  NISAR GCOV -> data/interim/stack.nc
src/blindspot/s2_change/     WS2  stack -> change.nc, patches.geojson, timeseries.json, synthetic_curve.json
src/blindspot/s3_fire/       WS3  FIRMS -> hotspots.geojson; cross-check -> crosscheck.csv, crosscheck_stats.json
src/blindspot/s4_validate/   WS4  RADD, sample, review.csv, validation_stats.json
src/blindspot/s5_package/    lead: merges everything into web/data/
src/blindspot/s6_context/    WS6  PSI and EONET context data
web/                         WS5  static app (Leaflet + Chart.js, no build step)
scripts/make_fixtures.py     synthetic data tree in data/fixtures/ matching every contract
scripts/run_pipeline.py      runs S2 to S5 (+ checks); --fixtures for demo data
docs/BRIEF.md                full project brief (problem, evidence, method, risks, sources)
docs/CONTRACTS.md            exact file formats between workstreams
docs/TEAM_PLAN.md            owners, timeline, gates, git workflow
docs/workstreams/WS*.md      step-by-step guide per workstream
docs/DATASETS.md             exact dataset IDs, links, filters, right/wrong checks
docs/DATA_REGISTER.md        every external source, licence, date
```

## 4. Rules for any assistant editing this repo

1. **Stay in the user's workstream folder.** Ask before changing files owned by another workstream (see `docs/TEAM_PLAN.md`). Never edit `web/data/` by hand; only `s5_package` writes it.
2. **Contracts are fixed.** Outputs must pass `python -m blindspot.contracts <name>`. Do not rename files, fields, labels or IDs. Adding optional fields is fine; document them in `docs/CONTRACTS.md`. Breaking changes follow "Changing a contract" in that file.
3. **Use `config.py`** for the grid, dates, paths and parameters. Never hard-code them elsewhere.
4. **Test on fixtures first:** `make demo` then `make check`. Real data goes in `data/` (git-ignored except `data/processed/` and `web/data/`).
5. **Wording:** say "change with no hotspot recorded", never "missed fire", "illegal" or "culprit". Radar change is a candidate disturbance until reviewed.
6. **Data policy:** use only the sources, IDs and filters in `docs/DATASETS.md`; only NASA, Copernicus and other openly licensed global data. No concession or ownership maps, no company names, nothing from Indonesian government platforms. Add every new source to `docs/DATA_REGISTER.md`.
7. **No invented numbers.** Figures in docs, slides or the app must come from pipeline outputs or a cited source in `docs/BRIEF.md`. If unsure, say so.
8. **Never commit secrets.** Keys live in `.env` (see `.env.example`).
9. Python ≥ 3.10, numpy/xarray/rasterio/geopandas/shapely 2; vectorise; keep functions small with docstrings. Web: plain JS, no frameworks or build tools.
10. Small PRs using the template; CodeRabbit reviews automatically; respond to its comments.

## 5. Key facts (for answering teammates' questions)

- Grid: EPSG:32749, 60 m, bounds (652860, 9654360, 702840, 9704340), 833 × 833. Box (112.375, -3.125, 112.825, -2.675).
- Dates: 2026-06-18, 06-30, 07-12, 07-24, (early-Aug missing), 08-17, 08-29, 09-10, 09-22, 10-04, 10-16, 10-28. Reference = the four June/July dates. 28 Oct uses processing P05036; the rest P05023.
- Collections: `NISAR_L2_GCOV_PROVISIONAL_V1`, `NISAR_L2_GCOV_V1`, `NISAR_L3_SME2_PROVISIONAL_V1`; dual-pol granules contain `4005_DHDH`.
- Context: Singapore PSI unhealthy from 4 Sep 2026, peak 192 on 9 Oct (NEA). About 202,004 ha burned in Indonesia by July 2026.
- Judging: Impact, Creativity, Validity, Relevance, Presentation, equal weight, 1 to 5. Demo: ≤ 7 slides or ≤ 30 s video. Submit by 23:59 SGT 15 Nov; team target 23:00.

## 6. Hand-off: what every workstream must deliver to the repo (assistants: enforce this)

The integration run happens on a different machine, by the lead or by an AI assistant without anyone's logins. It **cannot** run downloads that need a teammate's account (Earthdata, FIRMS key, Earth Engine, Giovanni), cannot see files left on a teammate's laptop, and is not notified when someone pushes. So **a workstream is not done until its outputs are in the repo or the data release.** If you are an AI helping a teammate, check this list before saying their work is finished, and remind them before every gate (09:00, 14:00, 19:00 SGT).

| WS | Commit to git (via PR) | Upload to release `data-v1` | Deadline |
|---|---|---|---|
| WS1 | code; `data/raw/granules.json` (force-add: `git add -f`) | `data/interim/stack.nc` | 09:00 SGT |
| WS2 | code; `data/processed/patches.geojson`, `timeseries.json`, `synthetic_curve.json`, `s2_sensitivity.csv` | `data/interim/change.nc` | 14:00 SGT |
| WS3 | code; `data/processed/hotspots.geojson`, `crosscheck.csv`, `crosscheck_stats.json`; `data/raw/firms/coverage.json` (force-add: `git add -f`) | the raw FIRMS CSVs zipped as `firms_raw.zip` | 14:00 SGT |
| WS4 | code; `data/processed/review.csv`, `reference_sample.csv` (labelled), `strata_pixel_counts.json`, `radd_by_patch.json`, `validation_stats.json`, `rain_daily.csv` | `data/raw/radd_alerts.tif`, `data/processed/peat_mask.tif` | 19:00 SGT |
| WS5 | everything under `web/` except `web/data/` | nothing | 19:00 SGT |
| WS6 | code; `data/processed/psi_daily.csv`, `eonet_events.geojson`; `story/` (script, slides or video link, `qa.md`, References text) | the video file if any | 19:00 SGT |

Rules for the hand-off:
1. Run `python -m blindspot.contracts <name>` on every output and paste the result in the PR.
2. Release upload (needs the GitHub CLI `gh`, logged in with `gh auth login`, and write access to the repo): `gh release create data-v1 --title "data v1" --notes "shared data" || true` then `gh release upload data-v1 <file> --clobber`. Post the file name in the team chat.
3. Merge the PR (or ask the lead to) before the deadline. Unmerged branches are invisible to integration.
4. If something will be late or missing, say so in the team chat before the gate, and name the fallback from your guide. A missing input is skipped by packaging, not fatal, but the lead must know.
5. Never commit secrets, and never commit files over ~50 MB to git; use the release.

# Team plan: six people, six machines, one product

The project is split so that **nobody waits for anybody**. Each workstream owns one folder and produces files with a fixed format (`docs/CONTRACTS.md`). Until the real upstream file exists, you build against the synthetic copy in `data/fixtures/`. At the end the integration lead runs one command and everything connects.

Before downloading anything, read [`DATASETS.md`](DATASETS.md): exact links, IDs and filters for every source.

## Who does what

Write your name and GitHub username in the table in your first PR.

| WS | Name | Owner | Folder you own | You produce | Guide |
|---|---|---|---|---|---|
| WS1 | Radar ingest | Falih (@Falih2007) | `src/blindspot/s1_ingest/` | `stack.nc` | [WS1](workstreams/WS1_radar_ingest.md) |
| WS2 | Change detection | name | `src/blindspot/s2_change/` | `change.nc`, `patches.geojson`, `timeseries.json`, `synthetic_curve.json` | [WS2](workstreams/WS2_change_detection.md) |
| WS3 | Fire record | _name_ | `src/blindspot/s3_fire/` | `hotspots.geojson`, `crosscheck.csv`, `crosscheck_stats.json` | [WS3](workstreams/WS3_fire_record.md) |
| WS4 | Validation and evidence | _name_ | `src/blindspot/s4_validate/` | `review.csv`, `reference_sample.csv`, `validation_stats.json`, `rain_daily.csv`, `peat_mask.tif` | [WS4](workstreams/WS4_validation.md) |
| WS5 | Web app | Abdallah (@abd2467) | `web/` (not `web/data/`) | the deployed site | [WS5](workstreams/WS5_web_app.md) |
| WS6 | Story, context, submission | _name_ | `src/blindspot/s6_context/`, `story/` | `psi_daily.csv`, `eonet_events.geojson`, slides or video, References | [WS6](workstreams/WS6_story_submission.md) |
| Lead | Integration | Abdallah (@abd2467) | `config.py`, `contracts.py`, `s5_package/`, `scripts/`, `docs/` | `web/data/`, merges, final run | this page |

The integration lead can also hold one workstream. Pair the two lightest loads if someone drops out: WS6 + WS5, or WS4 + WS3.

## Timeline (Singapore time, UTC+8)

Deadline: **Sun 15 Nov 23:59**. We submit at **23:00**.

| When | What | Gate |
|---|---|---|
| Sun 00:45 to 01:30 | Everyone: clone, `make setup`, `make demo`, open the app on fixtures, claim a workstream, create logins (Earthdata, FIRMS MAP_KEY, Earth Engine for WS4) | Everyone has run the demo |
| 01:30 to 03:00 | Start long jobs first: WS1 streams granules, WS3 downloads FIRMS, WS6 pulls PSI and EONET, WS4 starts RADD export | Downloads running |
| 03:00 to 08:00 | Sleep in shifts. Keep at least one download running. Build against fixtures when awake | |
| **09:00** | **Gate 1:** real `stack.nc` uploaded (release `data-v1`) | Fallback: 6 dates (18 Jun, 17 Aug, 10 Sep, 22 Sep, 4 Oct, 16 Oct) or ascending track 125 |
| 09:00 to 14:00 | WS2 runs on real stack; WS3 cross-check; WS4 sample and labelling; WS5 wires real data; WS6 drafts slides | |
| **14:00** | **Gate 2:** real headline number with a range in `crosscheck_stats.json` | Fallback: patch counts and area without Monte Carlo |
| 14:00 to 19:00 | Synthetic test, Monte Carlo, Olofsson CI, review of 10+ patches, app polish | |
| **19:00** | **Integration freeze:** last data PRs merged; lead runs `make real` and deploys | |
| 19:00 to 21:00 | Video or slides recorded on the deployed app; README and References final | |
| **21:00** | **Feature freeze** | |
| 21:00 to 23:00 | Submit on the Project tab; check it says submitted. Polish only | **23:00 submitted** |

Check in on the team chat at every gate: one line each, "done / blocked by X / fallback taken".

## Git workflow

1. `main` always runs. Never push to it directly.
2. Branch per task: `ws2/omnibus-alpha-sweep`, `ws5/patch-panel`, `lead/package-peat`.
3. Only change files in your own folder. Need a change elsewhere? Open an issue or ask the owner.
4. Before a PR: `make check` (runs tests and contract checks on fixtures).
5. Open a PR using the template. **CodeRabbit reviews it automatically**; fix or answer its comments. One teammate approves; the integration lead merges.
6. Keep PRs small and merge often. Rebase on `main` before pushing again: `git pull --rebase origin main`.

## Sharing data between machines

| What | Where |
|---|---|
| Code, small outputs (`data/processed/*.geojson/csv/json`, `web/data/`) | Git |
| Large files (`stack.nc`, `change.nc`, `radd_alerts.tif`) | GitHub release assets: `gh release create data-v1 --title "data v1" --notes "..."` once, then `gh release upload data-v1 data/interim/stack.nc --clobber`. Download: `gh release download data-v1 -D data/interim -p stack.nc` |
| Secrets (keys, passwords) | Your own `.env` only. Never commit them |

## Keeping the map current (lead)

`docs/floorplan.html` is a Floorplan export. After big merges, in Claude Code with the Floorplan plugin: ask "Update the floorplan", then run `node floorplan/serve.mjs --export docs/floorplan.html --include flows,notes` and commit the HTML. The `floorplan/` working folder stays out of git.

## Integration day procedure (lead)

```bash
git pull
gh release download data-v1 -D data/interim -p 'stack.nc' -p 'change.nc' --clobber
make real            # runs S2 -> S5 on real data and all contract checks
make serve           # http://localhost:8000, click through every panel
git add web/data data/processed && git commit -m "data: integrate real results" && git push
```

If a stage fails, the contracts tell you whose file is wrong. Fix or roll back that one input; everything else keeps working because S5 skips missing inputs.

## Hand-off checklist (the integration run can only use what is in the repo)

The integrator, whether the lead or an AI assistant, has none of your logins and cannot run your downloads. Whatever you leave on your laptop does not exist for integration. The exact files each workstream must commit or upload, with deadlines, are in [`AGENTS.md` section 6](../AGENTS.md#6-hand-off-what-every-workstream-must-deliver-to-the-repo-assistants-enforce-this). Your AI assistant reads that file and should remind you.

## Definition of done (per workstream)

- Output file passes `python -m blindspot.contracts <name>`.
- Outputs are **in the repo or the `data-v1` release, and the PR is merged** (AGENTS.md section 6). Work left on your machine counts as not done.
- Step list in your guide is ticked off, or the unfinished steps are written in your PR as "not done".
- Every external source you used is in `docs/DATA_REGISTER.md`.
- No claim stronger than the evidence ("no hotspot recorded", not "missed fire").

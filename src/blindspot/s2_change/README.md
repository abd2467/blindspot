# WS2 implementation and hand-off

See [VALIDATION.md](VALIDATION.md) for the feature audit, measured fixture results
and unresolved requirements, including the six-date fallback reference issue.

All commands below run from the repository root with `PYTHONPATH=src`.
Set `BLINDSPOT_DATA=data/fixtures` for demo checks. Unset it for real inputs.
On Windows, use `.venv\Scripts\python.exe` if the dependencies are in the local environment.

```text
python scripts/run_pipeline.py --fixtures
python -m pytest tests src/blindspot/s2_change/tests -q
python -m blindspot.contracts all
python -m blindspot.s2_change.sensitivity --half all
```

The pipeline command is the Windows equivalent of `make demo`. `make check`
generates fixtures, runs the repository tests and checks fixture contracts; run
the explicit WS2 test directory too, since the shared pytest configuration only
discovers `tests/`. Integration checks regenerate `web/data/` through S5.

## Detection

`python -m blindspot.s2_change.detect` writes `change.nc`, `patches.geojson` and
`timeseries.json` in the locations defined by `config.py`. It records the method,
alpha or threshold, measured effective looks, smoothing, minimum patch area and
normalisation source in the NetCDF method attribute. Contract fields are unchanged.

The likelihood ratio factors follow equations 1 and 3 of
[Canty et al. (2020), section 2](https://www.mdpi.com/2072-4292/12/01/46).
The existing implementation uses the first-order chi-square approximation for
diagonal dual-pol intensities (two degrees of freedom per sequential factor),
without the paper's finite-sample corrections. Alpha is nominal: whole-record
gating, directional selection, persistence and area filtering affect the final
false-alarm rate. Null-speckle calibration tests cover the omnibus statistic and
the first-change selector; real-data calibration is still required.

Effective looks are estimated from pooled temporal reference moments after
smoothing and normalisation: `sum(mean**2) / sum(sample_variance) - 1/n_reference`.
The subtraction corrects the contribution of temporal sampling variance to the
squared sample mean. A synthetic gamma-speckle regression checks this estimator.
The upstream `enl` argument is retained for API compatibility; measured looks
are used by the omnibus method. A zero-variance reference raises an error.

Pixels with missing, nonpositive or nonfinite power in either band at any date
are excluded conservatively. Smoothing cannot make those pixels eligible.
Only dates after the configured reference period can become first-change dates.
Persistence is applied before selecting the first eligible statistical event,
and the configured minimum area is applied to 8-connected components in both
the raster and vector outputs. A single last-date drop cannot pass persistence.

Both normalisation functions accept a stable mask. CLI commands automatically
read `data/processed/stable_area.geojson` (under the configured data root) if
present, or accept `--stable-area PATH`. The file must contain reviewed polygons
with a coordinate system and overlap valid land. Absent a polygon, scene land
is used and recorded. An invalid supplied polygon raises an error. No polygon
has been invented: reviewing intact forest and hotspot absence needs real data.

`edge` marks patches touching the raster border or an invalid pixel's immediate
neighbourhood. Existing water, HH-rise and processing-version flags remain.
`rain` marks onset during the final two configured October acquisitions as a
seasonal caution; it is not evidence of measured precipitation.

Fallback: `python -m blindspot.s2_change.detect --method logratio --threshold auto`.
Auto uses the first percentile of reference ratios, with the same minimum
1 dB drop, persistence and patch-area requirements. Fixed thresholds are also
supported, and `--smooth 5` increases spatial averaging.

## Sensitivity and synthetic checks

`python -m blindspot.s2_change.sensitivity --half west` writes
`s2_sensitivity.csv` for alpha 0.001, the configured default, and 0.05, plus
log-ratio thresholds -2, -3, -4 and auto. It records area in hectares, patch count,
settings, fixture status and the selected half. It never overwrites the selected
production detection outputs. `--half east` selects patches by centroid longitude
relative to the midpoint of the configured box. Defaults require WS4 agreement
on west-half validation before reporting east-half performance.

`python -m blindspot.s2_change.synthetic --trials 3` writes `synthetic_curve.json`.
It uses the same detector and patch filter, excludes incomplete baseline pixels,
places injections after the reference dates, and requires enough remaining dates
for persistence. Square footprints round up to whole pixels; actual areas appear
in the note. Skipped placements have zero trials and a null detection rate.
Fixture output explicitly identifies synthetic input. False alarms are measured
on baseline-unchanged, untouched land and are conditional, not an independent
estimate of the nominal alpha. The minimum detectable area must be assessed on
real input before requesting a change to shared configuration from the lead.

## Remaining real-data work

The checkout initially contained no real `data/interim/stack.nc`. Fixture outputs
stay under `data/fixtures/`; they must not be copied into the real hand-off paths.
Once WS1 supplies the stack, check reference medians, review a stable polygon,
run detection and contracts (`change`, `patches`, `timeseries`), run the sensitivity
sweep and synthetic test, and inspect the raster and flags. The shared contract
checker currently has no standalone `synthetic_curve` or `s2_sensitivity` check;
inspect their JSON/CSV content without changing the shared contracts.

The WS2 hand-off remains incomplete until the real small outputs are committed
through a PR and merged, `change.nc` is uploaded to release `data-v1`, contract
results are pasted in the PR, and the team is informed. The guide's gate is
14:00 SGT. This implementation does not publish or merge anything.

# WS2 validation

Working branch: `ws2/change-detection`. Result: fixture validation passes;
real-data readiness and the documented six-date fallback are not complete.

## Reproducible checks

```text
python -m pytest tests src/blindspot/s2_change/tests -q
```

Result: **32 passed**. This includes the full fixture pipeline, existing omnibus
tests, detector regressions and new public-command workflow checks. Workflow
commands run with numerical runtime warnings treated as errors and write to
temporary input/output directories. The final integration run used an isolated
source snapshot so it did not regenerate the checkout's `web/data/`.

With `PYTHONPATH=src` and `BLINDSPOT_DATA=data/fixtures` in that snapshot:

```text
python -m blindspot.contracts all
python -m blindspot.s2_change.synthetic --trials 3
python -m blindspot.s2_change.sensitivity
```

All **12 available contract checks passed**: stack, change, patches, timeseries,
hotspots, crosscheck, crosscheck_stats, review, validation_stats, psi, rain and
events. Synthetic JSON and sensitivity CSV have no standalone shared contract
check; workflow tests inspect their contents and strict JSON validity instead.

Local full log: `.venv/ws2-validation-adjdfvkv/validation.log`. This is an ignored
local validation artifact, not a shared data hand-off.

## Feature coverage

| Feature or function | Result and evidence |
|---|---|
| Omnibus statistics and `first_change` | Passed existing detection and null-speckle tests, likelihood factorisation, invalid-series exclusion and later eligible-change selection |
| Effective looks | Pooled temporal estimator recovered known gamma-speckle looks within the regression tolerance; fixture effective looks were 44.3 |
| `normalise_scene` and stable-area normalisation | Passed a controlled widespread-change test with a stable mask; scene-wide gain removed while local loss was retained |
| Stable polygon loading | Both explicit `--stable-area` and automatic `processed/stable_area.geojson` loading passed; real reviewed forest polygon is still absent |
| `boxcar`, reference means and indices | Exercised through both methods; NaN filtering produces no infinities; configured reference dates are used |
| Persistence and invalid pixels | Both methods passed persistent-drop, water exclusion, missing-observation and last-date-drop tests |
| Log-ratio fallback | CLI passed fixed thresholds -2, -3, -4 dB and auto |
| Smoothing fallback | CLI passed `--smooth 5` |
| Minimum area and connectivity | 8-connected components below configured area removed; raster/vector area consistency checked |
| `change.nc` | Required variables, dimensions, integer/float dtypes, method settings and changed/first-change consistency checked |
| Patches and time series | Contracts, strict JSON, matching patch IDs, previous-date ordering, per-date array lengths and area totals checked |
| Empty change result | Empty feature collection and patch time series, finite reference series, all-zero changed mask and all-minus-one first-change raster passed |
| Flags | Controlled patches triggered every allowed flag: water, hh_rise, rain, edge and calibration; real-world flag interpretation remains unverified |
| Sensitivity sweep | Seven requested settings passed for all/west/east; file hashes confirmed selected detection outputs were preserved; separate geometry test confirmed halves partition patches |
| Synthetic burn command | Both methods ran reproducibly with the default seed; 24 size/drop combinations, trial counts, bounded rates, injection timing and fixture labelling checked |
| Bad options | Invalid alpha, even smoothing size, positive log-ratio threshold and zero synthetic trials failed before writing processed outputs |
| Downstream integration | Fixture S3, S4 and S5 pipeline and all available contracts passed |

Fixture truth centers: all eight burns and both clearings were detected at their
expected acquisition dates; the final-date flood was excluded. The resulting
mask contained 1,716 changed pixels. Center checks establish event/date recovery,
not complete boundary accuracy or a real-world accuracy estimate.

Independent null-speckle benchmark (seed 27, 11 dates, 160 by 160 pixels, looks 20):
the omnibus rejection rate was **1.0195%** at nominal alpha 1%. The directional
first-change selector's rate was **0.4961%** after gating. These are different
quantities; persistence and spatial filtering further alter final mask rates.
The implementation retains its documented first-order chi-square approximation.

Three-trial default-method fixture injection results at a 3 dB drop:

| Nominal area (ha) | Actual square area (ha) | Detection rate |
|---|---|---|
| 1 | 1.44 | 0/3 |
| 2 | 3.24 | 0/3 |
| 5 | 5.76 | 1/3 |
| 10 | 12.96 | 3/3 |
| 20 | 23.04 | 3/3 |
| 50 | 51.84 | 3/3 |

The measured conditional false-alarm rate was 0.00014 (0.014%). It is measured
on baseline-unchanged, untouched pixels, not an independent estimate of nominal
alpha. Three fixture trials are insufficient to establish a reliable real-data
minimum detectable area; the configured 1 ha minimum is not a claim of 80%
detection at that size. Shared configuration was not changed.

## Unresolved requirements

1. **Six-date fallback fails under the current reference configuration.** WS1's
   guide lists 18 June, 17 August, 10 September, 22 September, 4 October and
   16 October. Only 18 June is in `REFERENCE_DATES`. Calling `reference_indices`
   on this list reproduces `ValueError: At least two configured reference dates
   are needed`, affecting both methods. WS1/lead must provide at least two
   defensible reference acquisitions or agree an alternative ENL/reference
   strategy before using that fallback. Later dates must not simply be declared
   stable to bypass the requirement.
2. **No real stack is present in the checkout.** Real reference-period inspection,
   stable-forest review, full real-grid performance, meaningful real flag review,
   west-half RADD tuning and east-half reporting remain unverified.
3. **Rain is a seasonal caution.** The flag uses the final two configured dates;
   it does not verify a rainfall event. Measured rain context and interpretation
   belong to WS4.
4. **Default test discovery omits WS2's local test folder.** `make check` and plain
   `pytest` use the lead-owned `testpaths = ["tests"]`. Use the explicit command
   above to run all 32 checks. Adding this directory to shared CI discovery needs
   coordination with the lead; no shared configuration was edited.
5. **Real hand-off remains outstanding.** No real small outputs, uploaded
   `change.nc`, merged PR or team notification were produced by this validation.
   Fixture files must remain identified as synthetic.

# Synthetic examples

[中文示例说明](README.zh-CN.md)

The Arrhenius example and fixed-parameter Weibull example use invented inputs; they are not recommendations or validated field predictions. In the fixed-parameter example, time and scale share the declared unit; an exponential rate is expressed per that unit. The quantile is the time at a user-supplied failure probability. At time zero with a Weibull shape below one, hazard is singular and returned as `null` with a warning. A hazard or positive quantile outside floating-point representation is rejected; probabilities may round to zero or one at extreme exposure.

These examples do not fit data, calibrate a mechanism, or validate a market forecast. See the tests and installation instructions for the checked scope.

The request models for these three public calculators reject Python and JSON booleans in calculation parameters, times, probabilities and life-conversion inputs before float conversion. `true` is not a lifetime, shape, temperature or rate of 1. Ordinary integer/float, numeric-string and Decimal coercion is unchanged; existing range checks still apply. Genuine numeric zero remains valid where the model allows it, such as evaluation time zero or zero Celsius. The services recheck constructed or subsequently mutated requests before calculation. This input safeguard does not add models or establish engineering validity; optional governance metadata is unchanged.

The exponential fitting example has three exact failures and two right-censored observations. It estimates a constant rate under IID lifetimes and independent non-informative censoring; it does not verify these assumptions or provide intervals. Even one failure can produce a point estimate, but few failures trigger an uncertainty warning.

## Offline saved-result report

`synthetic_saved_report.py` reads the frozen synthetic `saved_results.json`, never calls a solver, and writes HTML only to an explicitly supplied existing directory. The Arrhenius fixture stores the previously printed six-decimal factor; it is a rounded display snapshot, not a full-precision calculation result; the original converted-life value was not captured, so null means not provided. Other examples in the fixture are synthetic stored outputs. The report displays only whitelisted fields and does not include charts, external resources, task databases or raw observations. Treat supplied records as user content; they are not verified by the renderer.

For example, after creating an empty directory `report-output` yourself, run:

```powershell
.\.venv\Scripts\python.exe -B -m examples.synthetic_saved_report --output-dir .\report-output --locale en
```

The fixed filename `reliability-report.html` is created exclusively: an existing file is not overwritten. The renderer itself does no file I/O; this example reads the bundled fixture and writes only the explicit destination.

A [static Chinese synthetic report](synthetic-report.zh-CN.html) is included for inspection. Its structure was checked automatically; browser visual inspection remains pending.

### Saved survival results (optional)

Add `--include-survival` to the command above to append the frozen `saved_survival_results.json` examples. The default three-record report is unchanged. A [Chinese five-record example](synthetic-survival-report.zh-CN.html) includes the two additional result kinds:

- `kaplan_meier` preserves the public estimator's counts, last observation time, failure-time rows and limitations with status `synthetic_case_checked`. Tied failures and censoring remain in their stored rows. An all-censored result has an empty row list; the report does not invent survival estimates, intervals or extrapolation.
- `zero_failure_binomial` preserves the zero-event count, sample size, one-sided confidence level, upper probability, event definition, observation window, assumptions and limitations. Its status remains `experimental_synthetic_checks_only`. The bound is a probability for the stated test window, not a time rate or field forecast.

The snapshots use the public examples: three failures at 1, 2 and 2 hours with censoring at 2 and 3 hours, and zero failures among 100 synthetic units at confidence 0.95. The renderer does not call either estimator or recompute their answers. It checks display field shapes and basic ranges, not statistical correctness, assumptions, source authenticity or engineering suitability. Unknown top-level data fields are omitted; extra fields inside Kaplan–Meier rows are rejected. Field labels are bilingual; stored values and their original warning/limitation text remain unchanged. No chart or new dependency is introduced. Browser visual review and Windows verification of this extension remain pending.

See the [Kaplan–Meier synthetic example](KAPLAN_MEIER.md) for exact failures and right-censored observations, assumptions, and limitations.

See the [optional domain configuration example](DOMAIN_CONFIG.md); format checks do not validate engineering suitability.

Experimental [zero-failure binomial bound](ZERO_FAILURE.md), for a defined test window.


## Synthetic point scatter

See [the standalone scatter example and contract](SYNTHETIC_POINT_PLOT.md) for caller-declared synthetic points, display-only scope, validation evidence and limitations. No report or dispatcher integration.

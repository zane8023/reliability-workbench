# Synthetic examples

[中文示例说明](README.zh-CN.md)

The Arrhenius example and fixed-parameter Weibull example use invented inputs; they are not recommendations or validated field predictions. In the fixed-parameter example, time and scale share the declared unit; an exponential rate is expressed per that unit. The quantile is the time at a user-supplied failure probability. At time zero with a Weibull shape below one, hazard is singular and returned as `null` with a warning. A hazard or positive quantile outside floating-point representation is rejected; probabilities may round to zero or one at extreme exposure.

These examples do not fit data, calibrate a mechanism, or validate a market forecast. See the tests and installation instructions for the checked scope.

The exponential fitting example has three exact failures and two right-censored observations. It estimates a constant rate under IID lifetimes and independent non-informative censoring; it does not verify these assumptions or provide intervals. Even one failure can produce a point estimate, but few failures trigger an uncertainty warning.

## Offline saved-result report

`synthetic_saved_report.py` reads the frozen synthetic `saved_results.json`, never calls a solver, and writes HTML only to an explicitly supplied existing directory. The Arrhenius fixture stores the previously printed six-decimal factor; it is a rounded display snapshot, not a full-precision calculation result; the original converted-life value was not captured, so null means not provided. Other examples in the fixture are synthetic stored outputs. The report displays only whitelisted fields and does not include charts, external resources, task databases or raw observations. Treat supplied records as user content; they are not verified by the renderer.

For example, after creating an empty directory `report-output` yourself, run:

```powershell
.\.venv\Scripts\python.exe -B -m examples.synthetic_saved_report --output-dir .\report-output --locale en
```

The fixed filename `reliability-report.html` is created exclusively: an existing file is not overwritten. The renderer itself does no file I/O; this example reads the bundled fixture and writes only the explicit destination.

A [static Chinese synthetic report](synthetic-report.zh-CN.html) is included for inspection. Its structure was checked automatically; browser visual inspection remains pending.

See the [Kaplan–Meier synthetic example](KAPLAN_MEIER.md) for exact failures and right-censored observations, assumptions, and limitations.

See the [optional domain configuration example](DOMAIN_CONFIG.md); format checks do not validate engineering suitability.

# Synthetic result scatter plot (source preview)

Revised integration candidate, 2026-11-08, based on public commit `020b28610d9b8bd66200c6543b1af4a7097cc377`. This preview is not a tagged release or an accepted engineering workflow.

## Scope and privacy

`render_synthetic_result_scatter` displays one series of caller-supplied result points as a standalone in-memory SVG asset. It does not fit distributions, join/interpolate data points, draw probability plots, calculate intervals, forecast, or recalculate results. It is not connected to the dispatcher or HTML report renderer. Existing calculator and report behavior is unchanged.

`data_origin: "synthetic"` is only the caller's assertion. The output explicitly sets `origin_verified=False`; the program does not authenticate the origin, correctness, units or meaning of the points. Do not supply customer, company, personal or other real-world records to this demo. Labels and normalized point values are included in the returned asset metadata as well as the SVG.

## Input contract

The request must be an ordinary `dict` containing exactly `data_origin`, `title`, `estimand`, `x_axis`, `y_axis`, and `points`. No unknown or missing fields are accepted. The origin marker must be the exact string `synthetic`.

- `title` and `estimand`: ordinary strings, nonempty after trimming, maximum 120 and 100 characters respectively.
- Each axis: ordinary `dict` with exactly `label` and `unit`. Both are trimmed nonempty strings, maximum 80 and 40 characters respectively. All values on an axis must use that declared unit; inconsistent units cannot be detected.
- `points`: ordinary list of 1 to 100 ordinary dictionaries. Each point requires `x` and `y`, with optional `label`, and no other fields. A supplied label is a trimmed nonempty string of at most 80 characters. Omitted labels become `Point N` in input order.
- Coordinates: exact Python `int` or `float`, converted to finite binary64. Booleans, numeric strings, subclasses, NaN, infinity, and integers that overflow conversion are rejected. Finite integers beyond binary64's exact range can lose precision. Metadata preserves the converted values, not arbitrary-precision originals.
- All text must contain XML 1.0 characters only. Invalid shape, type, count, text or number raises `ValueError`; no partial asset is returned. This is an in-process Python contract, not an HTTP endpoint or JSON parser.

## Display and output

The fixed SVG canvas is 720 by 500, with five evenly spaced ticks per axis. Coordinate bounds are the series minimum and maximum. Low x is left, high x is right; low y is bottom, high y is top. Constant axes place all points at their midpoint. Tick text has five significant digits; plotted coordinates have six decimal places. This finite display precision is not additional analytical precision. Extremely close values may share tick labels or pixels. Tick labels still represent rounded display values, not exact source-value recovery.

Three display issues have been addressed: y-axis labels use the same low-to-high mapping as the circles; endpoint labels retain their supplied bounds; and interior ticks no longer lose small residuals through floating-point cancellation. For the five fixed tick fractions (0, 1/4, 1/2, 3/4, 1), the helper computes the weighted value exactly from the already-converted binary64 bounds using standard-library rational arithmetic, then converts once to binary64 for display. For example, bounds `-1e20` and `math.nextafter(1e20, math.inf)` now retain the midpoint `8192`, rather than showing `0`; the mirrored case retains `-8192`. This bounded arithmetic is used only for tick labels. Point coordinates, source values, validation and statistical behavior are unchanged. Finite span overflow and subnormal values are covered by the tick arithmetic; display conversion and five-significant-digit formatting still round values.

The renderer uses standard-library XML text nodes for escaping, with fixed SVG tags and attributes and no scripts or external resources. It makes no filesystem, network, database or process calls. The existing [asset wrapper](../app/services/saved_report.py) supplies Base64 content, SHA-256, byte length and the 8 MiB size cap. Bounded text and 100 points keep accepted payloads below this cap. It does not change global XML namespace registration.

## Example

```python
from app.services.synthetic_point_plot import render_synthetic_result_scatter

plot = render_synthetic_result_scatter({
    "data_origin": "synthetic",
    "title": "Synthetic reliability points",
    "estimand": "Reliability R(t)",
    "x_axis": {"label": "Time", "unit": "hour"},
    "y_axis": {"label": "Reliability", "unit": "probability"},
    "points": [
        {"x": 0.0, "y": 1.0, "label": "start"},
        {"x": 100.0, "y": 0.99, "label": "point 1"},
    ],
})
print(plot["mime_type"], plot["sha256"], plot["point_count"])
```

## Validation and provenance limits

On 2026-11-08, this revision passed 83 targeted tests: 25 scatter tests and 58 existing saved-report, saved-survival-report and dispatcher tests, with no failures, errors or skips. The preceding 20 scatter methods are AST-identical; five new methods check interior cancellation, quarter ticks, finite extreme ranges, subnormal rounding and both SVG axes. On the unchanged v2 renderer, three of the five new methods expose defects, producing 26 failing subtest entries and no execution errors; the other two already pass. All five pass on v3. The v2 results and limitations remain historical evidence, not claims about this revision. Both bilingual code examples executed successfully and 65 repository Markdown local links resolved. Environment: Linux x86_64, Python 3.12.14, Pydantic 2.13.4, NumPy 2.3.5, SciPy 1.17.0; no dependency installation or change. These are scoped checks, not a complete-suite claim.

Browser visual inspection, long-label/font/localization legibility, full-suite execution, Windows execution, installation, HTTP security and VDI acceptance are not established by these checks. SVG labels may overlap or be clipped in the fixed layout. This display aid is not engineering evidence or a product-life guarantee.

The renderer and original six tests come from the supplied isolated public-source preview. The original renderer SHA-256 was `24815a4d9eb17bf10906567d649a6f4c5e2146e237e9f25fa61b40d499dbfdf4`; the original test SHA-256 was `31fbf1352b686e0cb3a49f1d03501273281545e487e08d41355c85938f1809cd`. This integration adds the three display repairs, fresh regressions and updated documentation. It does not import the internal report bridge or claim that the full private project is redistributable. Existing [LICENSE](../LICENSE), [NOTICE](../NOTICE) and [third-party review](../THIRD_PARTY_REVIEW.md) are retained unchanged; no dependency or third-party distribution is added. Source review and matching hashes are not an independent legal certification of ownership or rights.

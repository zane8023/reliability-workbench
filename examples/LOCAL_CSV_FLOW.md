# In-process CSV → exponential point estimate → report candidate

This is an experimental in-process source preview, not a web app, network service, file uploader, database, or complete workbench. `analyze_csv(raw, time_unit, locale)` accepts CSV **bytes**, one time unit, and `en`/`zh-CN`, using the local parser and published exponential estimator and report renderer in the calling process. It accepts no path and provides no network listener, authentication, or persistence; do not expose it as a multi-user service.

The data below is invented. This integration candidate uses reviewed public baseline `c2a0101ec3961f863e0189afd4aaecb1bc5d775e`, preserving its later input-validation and report fixes. From this candidate's source directory in an isolated environment, run:

```python
from local_csv_exponential_flow import analyze_csv
raw = b"kind,time\nexact,1\nexact,2\nexact,3\nright_censored,4\nright_censored,5\n"
answer = analyze_csv(raw, "hour", "en")
assert answer["ok"] and answer["result"]["total_exposure"] == 15.0
assert answer["result"]["scale"] == 5.0
```

## CSV input contract

- Supply a `bytes` value containing 1 to 65,536 bytes, including any UTF-8 BOM. Decode as UTF-8 with an optional leading BOM; NUL characters and invalid UTF-8 are rejected. LF and CRLF line endings and CSV-quoted fields are supported.
- The parsed header must be exactly `kind,time`, in that order, with no duplicate or extra columns. Each data row must contain exactly two fields. Blank data rows are rejected; a normal final line ending is allowed.
- Supply 1 to 5,000 data rows. Each parsed data cell may contain at most 64 characters. Event kind must be exactly `exact` or `right_censored`.
- Time uses ASCII decimal syntax, optionally signed, with an optional decimal point and `e`/`E` exponent. Examples include `1`, `1.5`, `.5`, `1.` and `2e0`. Whitespace, underscores, NaN and infinity are rejected. The decimal value must be greater than zero and no greater than `2**53` (9,007,199,254,740,992); conversion must produce a finite positive binary float. Conversion may round. Extremely small accepted values can still fail during estimation when the rate cannot be represented.
- Pass exactly one unit: `second`, `minute`, `hour`, `day` or `year`. It labels all observations; this adapter does not infer or convert mixed units. Locale must be `en` or `zh-CN`.

Format errors return parser codes and available physical line numbers without echoing raw cells. With no exact failures the flow returns `NO_OBSERVED_FAILURES` before fitting. Numeric/report failures return `FIT_OR_REPORT_FAILED`, ordinary unexpected exceptions return `INTERNAL_ERROR`; `MemoryError` propagates rather than being reported as a successful calculation.

Time values may round during conversion to binary floats; success includes a warning, which does not prevent precision loss. The response contains **individual normalized observations**, the result and a Base64 HTML summary, and may be sensitive. Callers must protect process memory and results from unintended logging or transmission. The selected-field report is not a complete reproducible archive. The exponential distribution and independent non-informative censoring are assumptions for users to validate; preserve warnings for few failures. No confidence interval, Weibull fitting, field forecast, or chart is provided.

Local tests block some common file-open and socket-connect calls and check the fit count; they do not prove that all dependencies or callers avoid I/O. The operating system can still swap memory or log information. The candidate imports a generic `app` name whose source was verified only in the isolated test copy, and it may conflict elsewhere. Real file paths, links, Excel, persistence, authentication, multi-user use, visual review, full end-to-end operation, and VDI remain unverified; publication of this source does not validate deployment or broader workbench readiness.

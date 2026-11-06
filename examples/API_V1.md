# Experimental in-process dispatcher contract

[中文](API_V1.zh-CN.md) | [Project](../README.md)

Experimental source preview added on 2026-11-06 over reviewed public commit `addfb5aedf15eb8fb3c7c2a92f2ddebfde441b7e`. This is a Python source adapter, not a running HTTP API, web workbench, installation package, or deployment. No listener, database, session, authentication, file upload, AI service or persistent storage is added. The original public calculators and report renderer are unchanged.

## Entry points and data boundary

- `dispatch(operation, envelope)` accepts a supported operation string and a JSON-shaped Python dictionary. `operation` is a separate argument, not a request-body field.
- The envelope must contain `contract_version: "1"` and an `input` object, with no other top-level fields. The operation-specific input is validated before calling the public function. Numeric strings and boolean substitutes for calculation numbers are rejected; ordinary JSON integers and floats remain supported where the underlying model permits them.
- `parse_json_body(body)` is an optional bytes-to-value helper. It accepts at most 1,048,576 bytes of strict UTF-8 JSON and rejects duplicate keys, literal NaN/Infinity and float exponent overflow such as `1e309`. It may return any JSON root value; `dispatch` then requires an object envelope. Non-bytes input raises `TypeError`; malformed, oversized, duplicate-key, nonfinite-number or UTF-8 input raises `ValueError` or its subclasses. Parser failures are not dispatcher error envelopes.
- The byte limit applies to that parsing helper, not to an already-parsed dictionary. Callers own transport, logging, resource and text-encoding policies. No additional nesting/node budget, cancellation, timeout or network-security guarantee is provided. Normal binary64 rounding, including tiny decimal values rounding to zero, still applies; this is not arbitrary-precision decimal input.
- Requests/results are handled in memory. Successful results can include supplied observations, parameters or labels, and reports contain Base64 HTML. Do not log or transmit them unintentionally. Failure messages do not echo submitted keys, values or original exception text. This does not certify every dependency or caller as free of I/O.

## Supported operations

| Operation | Input contract | Result and boundary |
| --- | --- | --- |
| `arrhenius.evaluate` | `model_name: "arrhenius"`; numeric `parameters` with `activation_energy`, `test_temperature`, `use_temperature`; units `temperature_unit` (`K` or `degC`), `activation_energy_unit` (`eV` or `J/mol`), `humidity_unit` (`fraction` or `percent`) retain public defaults. Optional `life_conversion` is null or an object containing only `input_life`, `input_condition` (`test` or `use`) and `time_unit`. | Published forward acceleration factor and optional life conversion. Internal governance input is not accepted. Known but unavailable acceleration models return `unsupported_model`; an invalid model spelling returns `invalid_input`. No formal field-failure eligibility is granted. |
| `reliability.evaluate` | `model` is `weibull` or `exponential`; `parameters` are exactly `{scale, shape}` or `{failure_rate}` respectively; `time`, `time_unit`, optional `quantile_probability` (default 0.1). | Fixed-parameter reliability, failure probability, hazard and quantile. This is not Weibull fitting. Valid zero-time behavior and existing numerical range guards remain unchanged. |
| `exponential.fit` | `observations`: 1–10,000 objects containing only `kind` (`exact` or `right_censored`) and numeric positive `time`; `time_unit`. | Exponential point MLE. At least one exact failure is required. No confidence interval or forecasting is added. |
| `kaplan_meier.estimate` | `failures` list; optional `right_censored` list (default empty); explicit nonempty `time_unit` label. Combined count 1–10,000, nonnegative finite numbers. | Original event/risk-set point estimates. Zero times and all-censored data remain valid. The function accepts a nonempty unit label, not the narrower unit enum used by the other time-based models; it does not detect mixed units. |
| `zero_failure.upper_bound` | Integer `sample_size` from 1 to 10,000,000; numeric `confidence_level` strictly between 0 and 1; meaningful UTF-8 `event_definition` and `observation_window` strings, each at most 500 characters. | Exact one-sided binomial probability upper bound for the declared window, not a time rate or field forecast. |
| `report.render_saved` | `records` list of `{kind, data}` objects; optional `locale` (`en`, default, or `zh-CN`) and `title` (null/default, or 1–160 characters). | Display-only HTML asset with MIME type, byte size, SHA256 and Base64 bytes. No calculation or file write is performed by the renderer. |

Arrhenius life conversion, fixed reliability and exponential fitting use `second`, `minute`, `hour`, `day` or `year`. The existing model-specific constraints still apply. The adapter does not apply exponential positivity/failure-count requirements to Kaplan–Meier.

The five saved-report kinds are `arrhenius`, `fixed_reliability`, `exponential_fit`, `kaplan_meier` and `zero_failure_binomial`. Use complete stored results with their original validation status, assumptions and warnings. The renderer displays selected fields and does not independently verify their arithmetic or engineering suitability. It permits 1–25 records, at most 256 KiB of its serialized records input, and an 8 MiB output asset. Unknown metadata inside a result is not automatically displayed. There are no charts.

Nelson–Aalen is separately available in the public source, but this dispatcher has no Nelson operation and its saved-report renderer does not accept a Nelson kind. CSV flow, domain-format checking, generic solving, HTTP routes and original workflow features are also not new dispatcher operations.

## Synthetic example

Run from this project's source directory with the project's dependencies available. No file is created.

```python
import base64
import hashlib
from app.api_v1 import dispatch, parse_json_body

request = parse_json_body(b'{"contract_version":"1","input":{"time_unit":"hour","observations":[{"kind":"exact","time":1},{"kind":"exact","time":2},{"kind":"exact","time":3},{"kind":"right_censored","time":4},{"kind":"right_censored","time":5}]}}')
response = dispatch("exponential.fit", request)
assert "result" in response, response
result = response["result"]
assert result["total_exposure"] == 15.0
assert result["scale"] == 5.0
assert result["validation_status"] == "synthetic_case_checked"

saved = dispatch("report.render_saved", {
    "contract_version": "1",
    "input": {"records": [{"kind": "exponential_fit", "data": result}],
              "locale": "en", "title": "Synthetic point estimate"},
})
assert "result" in saved, saved
asset = saved["result"]
raw = base64.b64decode(asset["content_base64"], validate=True)
assert len(raw) == asset["byte_size"]
assert hashlib.sha256(raw).hexdigest() == asset["sha256"]
assert asset["presentation_only"] and not asset["calculation_performed"]

bad = dispatch("reliability.evaluate", {
    "contract_version": "1",
    "input": {"model": "exponential", "parameters": {"failure_rate": 0.2},
              "time": "1", "time_unit": "hour"},
})
assert bad["error"]["code"] == "invalid_input"
print("Synthetic exponential scale:", result["scale"], result["time_unit"])
```

Additional mathematical examples: [Arrhenius and fixed/exponential calculations](README.md), [Kaplan–Meier](KAPLAN_MEIER.md), [zero-failure bound](ZERO_FAILURE.md).

## Responses and errors

Success is `{"contract_version":"1","result":...}`. Results preserve the current public function's complete JSON-compatible output, including warnings and provenance when present. Arrhenius retains its original `formula_validation_status`/`validation_scope` fields. The other calculations retain their original `validation_status`; zero-failure remains `experimental_synthetic_checks_only`. The adapter never promotes a status.

Failure is `{"contract_version":"1","error":{"code":"...","message":"...","fields":[...]}}`:

- `unknown_operation`: unsupported operation name or non-string operation.
- `invalid_request`: non-object envelope/input, missing input or unknown envelope field.
- `unsupported_contract_version`: missing version, a non-string version or anything other than `"1"`.
- `invalid_input`: rejected operation fields, types, units, data or numerical range.
- `unsupported_model`: a recognized acceleration model outside the public Arrhenius scope.
- `internal_error`: unexpected failure, with details suppressed.

`fields` contains only safe schema-level paths or is empty; Pydantic failures currently use an empty list. There are no HTTP status codes or routes in this module. HTTP routes remain future work, not implemented services.

## Validation and provenance limits

The existing local dispatcher source and test were identified against their recorded hashes, then integrated as a narrow addition to the current public code. The repairs only tighten the adapter's input boundary and correct/add tests. Existing public calculators, renderer, CSV flow, Nelson implementation, licenses and dependency declarations are unchanged. The adapter adds no new dependency; applicable dependency licenses and inherited source-provenance limits still apply. This is not whole-project rights certification.

Focused verification can be run with `python -m unittest discover -s tests -p "test_api_v1.py" -v`. The 2026-11-06 integration passed 120 targeted tests (36 dispatcher tests and 84 affected existing tests), both bilingual examples and 40 local documentation links. It used Linux x86_64, Python 3.12.14, Pydantic 2.13.4, NumPy 2.3.5 and SciPy 1.17.0 without installing or changing dependencies; this does not establish fresh Windows/Python 3.10.11 compatibility. There is no new claim of a complete test-suite, browser visual, HTTP security, project-installation, VDI or field-use acceptance. Synthetic results do not validate model assumptions or suitability for decisions.

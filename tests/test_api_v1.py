"""Synthetic, transport-neutral regressions for the v1 dispatcher boundary."""
import base64
from contextlib import ExitStack
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import json
import math
import unittest
from unittest import mock

from app.api_v1 import MAX_OBSERVATIONS, MAX_REQUEST_BYTES, dispatch, parse_json_body
from app.services.exponential_fit import fit_exponential
from app.services.fixed_reliability import evaluate_fixed_reliability
from app.services.kaplan_meier import kaplan_meier
from app.services.saved_report import render_saved_report
from app.services.v3_accelerated_solver_service import V3AcceleratedSolverService
from app.services.zero_failure_binomial import zero_failure_upper
from app.validators.exponential_fit import ExponentialFitRequest
from app.validators.fixed_reliability import FixedReliabilityRequest
from app.validators.v3_accelerated_solver import V3AcceleratedLifeEvaluateRequest


def envelope(data):
    return {"contract_version": "1", "input": data}


def arrhenius_input():
    return {
        "model_name": "arrhenius",
        "parameters": {"activation_energy": 0.6, "test_temperature": 343.15,
                       "use_temperature": 298.15},
        "temperature_unit": "K", "activation_energy_unit": "eV",
        "humidity_unit": "fraction",
        "life_conversion": {"input_life": 100.0, "input_condition": "test",
                            "time_unit": "hour"},
    }


def fixed_input(model="weibull"):
    return {
        "model": model,
        "parameters": ({"scale": 1000.0, "shape": 2.0} if model == "weibull"
                       else {"failure_rate": 0.2}),
        "time": 100.0, "time_unit": "hour", "quantile_probability": 0.1,
    }


def exponential_input():
    return {"time_unit": "hour", "observations": [
        {"kind": "exact", "time": 1.0},
        {"kind": "right_censored", "time": 4.0},
    ]}


def km_input():
    return {"failures": [3, 7, 10], "right_censored": [5, 12], "time_unit": "hour"}


def zero_input():
    return {"sample_size": 100, "confidence_level": 0.95,
            "event_definition": "Synthetic event", "observation_window": "Synthetic window"}


def numeric_positions():
    """Every numeric input position, including both observation kinds/models."""
    cases = [
        ("arrhenius.evaluate", arrhenius_input(), [
            ("parameters", "activation_energy"), ("parameters", "test_temperature"),
            ("parameters", "use_temperature"), ("life_conversion", "input_life")]),
        ("reliability.evaluate", fixed_input(), [
            ("parameters", "scale"), ("parameters", "shape"),
            ("time",), ("quantile_probability",)]),
        ("reliability.evaluate", fixed_input("exponential"), [
            ("parameters", "failure_rate"), ("time",), ("quantile_probability",)]),
        ("exponential.fit", exponential_input(), [
            ("observations", 0, "time"), ("observations", 1, "time")]),
        ("kaplan_meier.estimate", km_input(), [("failures", 0), ("right_censored", 0)]),
        ("zero_failure.upper_bound", zero_input(), [("sample_size",), ("confidence_level",)]),
    ]
    for operation, payload, paths in cases:
        for path in paths:
            yield operation, payload, path


def replace_at(payload, path, value):
    changed = deepcopy(payload)
    target = changed
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return changed


def json_value(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.loads(json.dumps(value, allow_nan=False))


class ReportParser(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.tags, self.attributes, self.values = [], [], []
        self.buffer = None
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)
        if tag == "pre":
            self.buffer = ""

    def handle_data(self, data):
        if self.buffer is not None:
            self.buffer += data

    def handle_endtag(self, tag):
        if tag == "pre":
            self.values.append(json.loads(self.buffer))
            self.buffer = None


class ApiV1Tests(unittest.TestCase):
    def assert_result(self, operation, data):
        response = dispatch(operation, envelope(data))
        self.assertEqual(set(response), {"contract_version", "result"}, response)
        self.assertEqual(response["contract_version"], "1")
        json.dumps(response, allow_nan=False)
        return response["result"]

    def assert_error(self, operation, data, code="invalid_input"):
        response = dispatch(operation, envelope(data))
        self.assertEqual(set(response), {"contract_version", "error"}, response)
        self.assertEqual(response["contract_version"], "1")
        self.assertEqual(response["error"]["code"], code)
        self.assertEqual(set(response["error"]), {"code", "message", "fields"})
        json.dumps(response, allow_nan=False)
        return response

    def saved_records(self):
        cases = [
            ("arrhenius", "arrhenius.evaluate", arrhenius_input()),
            ("fixed_reliability", "reliability.evaluate", fixed_input()),
            ("exponential_fit", "exponential.fit", exponential_input()),
            ("kaplan_meier", "kaplan_meier.estimate", km_input()),
            ("zero_failure_binomial", "zero_failure.upper_bound", zero_input()),
        ]
        return [{"kind": kind, "data": self.assert_result(operation, data)}
                for kind, operation, data in cases]

    def test_arrhenius_synthetic_and_life_conversion(self):
        result = dispatch("arrhenius.evaluate", envelope({
            "model_name": "arrhenius",
            "parameters": {"activation_energy": 0.6, "test_temperature": 343.15,
                           "use_temperature": 298.15},
            "temperature_unit": "K", "activation_energy_unit": "eV",
            "humidity_unit": "fraction",
            "life_conversion": {"input_life": 100.0, "input_condition": "test",
                                "time_unit": "hour"},
        }))
        self.assertIn("result", result)
        self.assertTrue(math.isclose(result["result"]["acceleration_factor"],
                                     21.380333795562844, rel_tol=1e-12))
        self.assertFalse(result["result"]["ffr_formal_eligibility"])
        self.assertTrue(math.isclose(result["result"]["converted_life"]["value"],
                                     2138.0333795562844, rel_tol=1e-12))

    def test_fixed_reliability_closed_form(self):
        result = dispatch("reliability.evaluate", envelope({
            "model": "weibull", "parameters": {"scale": 1000.0, "shape": 2.0},
            "time": 100.0, "time_unit": "hour", "quantile_probability": 0.1,
        }))
        data = result["result"]
        self.assertTrue(math.isclose(data["reliability"], math.exp(-0.01), rel_tol=1e-14))
        self.assertTrue(math.isclose(data["failure_probability"], 1-math.exp(-0.01), rel_tol=1e-14))
        self.assertTrue(math.isclose(data["hazard_rate"], 0.0002, rel_tol=1e-14))
        self.assertTrue(math.isclose(data["quantile_time"], 324.59284597450124, rel_tol=1e-12))
        json.dumps(result, allow_nan=False)

    def test_exponential_exact_and_right_censored_reference(self):
        result = dispatch("exponential.fit", envelope({
            "time_unit": "hour",
            "observations": [
                {"kind": "exact", "time": 1}, {"kind": "exact", "time": 2},
                {"kind": "exact", "time": 3}, {"kind": "right_censored", "time": 4},
                {"kind": "right_censored", "time": 5},
            ],
        }))
        data = result["result"]
        self.assertEqual(data["failure_count"], 3)
        self.assertEqual(data["total_exposure"], 15.0)
        self.assertEqual(data["time_unit"], "hour")
        self.assertTrue(math.isclose(data["failure_rate"], 0.2, rel_tol=1e-14))
        self.assertTrue(math.isclose(data["scale"], 5.0, rel_tol=1e-14))

    def test_kaplan_meier_risk_set_reference_and_repeatability(self):
        data = {"failures": [3, 7, 10], "right_censored": [5, 12], "time_unit": "hour"}
        first = dispatch("kaplan_meier.estimate", envelope(data))
        second = dispatch("kaplan_meier.estimate", envelope(data))
        self.assertEqual(first, second)
        rows = first["result"]["rows"]
        estimates = [r["survival"] for r in rows if r["failures"]]
        # Rational reference values may round one ULP differently from the
        # published successive-product calculation. Repeatability stays exact.
        for actual, expected in zip(estimates, [0.8, 8/15, 4/15]):
            self.assertLessEqual(abs(actual - expected), math.ulp(expected))
        self.assertEqual(len(estimates), 3)
        self.assertEqual(first["result"]["time_unit"], "hour")
        self.assertNotIn("confidence_interval", first["result"])

    def test_zero_failure_exact_binomial_reference(self):
        result = dispatch("zero_failure.upper_bound", envelope({
            "sample_size": 100, "confidence_level": 0.95,
            "event_definition": "Synthetic event", "observation_window": "Synthetic window",
        }))
        self.assertTrue(math.isclose(result["result"]["failure_probability_upper"],
                                     0.02951304960703993, rel_tol=1e-13))
        self.assertEqual(result["result"]["failure_count"], 0)
        self.assertIn("not a", result["result"]["limitations"][0].lower())

    def test_saved_report_renders_snapshot_without_computation_claim(self):
        source = dispatch("reliability.evaluate", envelope({
            "model": "weibull", "parameters": {"scale": 1000.0, "shape": 2.0},
            "time": 100.0, "time_unit": "hour", "quantile_probability": 0.1,
        }))["result"]
        report = dispatch("report.render_saved", envelope({
            "records": [{"kind": "fixed_reliability", "data": source}], "locale": "en",
        }))
        self.assertTrue(report["result"]["presentation_only"])
        self.assertFalse(report["result"]["calculation_performed"])
        self.assertEqual(report["result"]["mime_type"], "text/html")
        self.assertTrue(report["result"]["content_base64"])

    def test_missing_unknown_and_version_errors_do_not_echo_payload(self):
        missing = dispatch("reliability.evaluate", {"contract_version": "1"})
        self.assertEqual(missing["error"]["code"], "invalid_request")
        bad_version = dispatch("reliability.evaluate", {"contract_version": "2", "input": {}})
        self.assertEqual(bad_version["error"]["code"], "unsupported_contract_version")
        unknown = dispatch("not.available", envelope({}))
        self.assertEqual(unknown["error"]["code"], "unknown_operation")
        malformed_operation = dispatch([], envelope({}))
        self.assertEqual(malformed_operation["error"]["code"], "unknown_operation")
        invalid = dispatch("zero_failure.upper_bound", envelope({
            "sample_size": 100, "confidence_level": 0.95,
            "event_definition": "SENSITIVE-MARKER", "observation_window": "window",
            "SENSITIVE-MARKER": "SENSITIVE-MARKER",
        }))
        self.assertNotIn("SENSITIVE-MARKER", json.dumps(invalid))
        nested = dispatch("reliability.evaluate", envelope({
            "model": "weibull", "parameters": {"scale": 1000, "shape": 2,
                                                   "SENSITIVE-MARKER": 1},
            "time": 100, "time_unit": "hour", "quantile_probability": 0.1,
        }))
        self.assertNotIn("SENSITIVE-MARKER", json.dumps(nested))

    def test_invalid_numbers_units_unknown_models_and_boolean_numeric(self):
        base = {"model": "weibull", "parameters": {"scale": 1000, "shape": 2},
                "time": 100, "time_unit": "hour", "quantile_probability": 0.1}
        for change in ({"time": True}, {"time": float("nan")}, {"time_unit": "fortnight"},
                       {"extra": "not-supported"}):
            payload = dict(base); payload.update(change)
            self.assertIn("error", dispatch("reliability.evaluate", envelope(payload)))
        unsupported = dispatch("arrhenius.evaluate", envelope({
            "model_name": "temperature_eyring",
            "parameters": {"activation_energy": 0.6, "test_temperature": 343.15,
                           "use_temperature": 298.15},
        }))
        self.assertEqual(unsupported["error"]["code"], "unsupported_model")
        invalid = arrhenius_input()
        invalid["model_name"] = "eyring"
        self.assert_error("arrhenius.evaluate", invalid)

    def test_observation_caps_missing_fields_and_incomplete_report(self):
        too_many = dispatch("kaplan_meier.estimate", envelope({
            "failures": [1.0] * 10_001, "right_censored": [], "time_unit": "hour",
        }))
        self.assertEqual(too_many["error"]["code"], "invalid_input")
        zero_missing = dispatch("zero_failure.upper_bound", envelope({"sample_size": 10}))
        self.assertEqual(zero_missing["error"]["code"], "invalid_input")
        km_report = dispatch("report.render_saved", envelope({
            "records": [{"kind": "kaplan_meier", "data": {}}],
        }))
        self.assertEqual(km_report["error"]["code"], "invalid_input")

    def test_json_parser_rejects_duplicate_keys_nonfinite_and_oversize(self):
        for body in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.assertRaises(ValueError):
                parse_json_body(body)
        with self.assertRaises(ValueError):
            parse_json_body(b" " * (1_048_576 + 1))
        with self.assertRaises(UnicodeDecodeError):
            parse_json_body(b"\xff")

    def test_report_html_escapes_title_and_rejects_bad_locale(self):
        fixed = dispatch("reliability.evaluate", envelope({
            "model": "exponential", "parameters": {"failure_rate": 0.2},
            "time": 1, "time_unit": "hour", "quantile_probability": 0.1,
        }))["result"]
        report = dispatch("report.render_saved", envelope({
            "records": [{"kind": "fixed_reliability", "data": fixed}],
            "title": "<synthetic>", "locale": "en",
        }))
        html = base64.b64decode(report["result"]["content_base64"]).decode("utf-8")
        self.assertIn("&lt;synthetic&gt;", html)
        self.assertNotIn("<synthetic>", html)
        bad_locale = dispatch("report.render_saved", envelope({
            "records": [{"kind": "fixed_reliability", "data": fixed}], "locale": "xx",
        }))
        self.assertEqual(bad_locale["error"]["code"], "invalid_input")

    def test_numeric_strings_are_rejected_at_every_numeric_position(self):
        for operation, payload, path in numeric_positions():
            target = payload
            for key in path:
                target = target[key]
            with self.subTest(operation=operation, model=payload.get("model"), path=path):
                self.assert_error(operation, replace_at(payload, path, str(target)))

    def test_booleans_are_rejected_at_every_numeric_position(self):
        for operation, payload, path in numeric_positions():
            for value in (True, False):
                with self.subTest(operation=operation, model=payload.get("model"), path=path, value=value):
                    self.assert_error(operation, replace_at(payload, path, value))

    def test_nonfinite_values_are_rejected_at_every_numeric_position(self):
        for operation, payload, path in numeric_positions():
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(operation=operation, path=path, value=value):
                    self.assert_error(operation, replace_at(payload, path, value))

    def test_nested_life_fields_are_allowlisted_without_echo(self):
        for value in ("SENSITIVE-LIFE-MARKER", {"nested": "SENSITIVE-LIFE-MARKER"}):
            payload = arrhenius_input()
            payload["life_conversion"]["SENSITIVE-LIFE-MARKER"] = value
            response = self.assert_error("arrhenius.evaluate", payload)
            self.assertNotIn("SENSITIVE-LIFE-MARKER", json.dumps(response))
        for invalid in ([], "SENSITIVE-LIFE-MARKER", 1):
            payload = arrhenius_input()
            payload["life_conversion"] = invalid
            self.assert_error("arrhenius.evaluate", payload)
        payload = arrhenius_input()
        payload["life_conversion"] = None
        self.assertIsNone(self.assert_result("arrhenius.evaluate", payload)["converted_life"])

    def test_dispatcher_strictness_does_not_change_public_validator_coercion(self):
        cases = [
            ("arrhenius.evaluate", V3AcceleratedLifeEvaluateRequest,
             replace_at(arrhenius_input(), ("parameters", "activation_energy"), "0.6")),
            ("reliability.evaluate", FixedReliabilityRequest,
             replace_at(fixed_input(), ("time",), "100.0")),
            ("exponential.fit", ExponentialFitRequest,
             replace_at(exponential_input(), ("observations", 0, "time"), "1.0")),
        ]
        for operation, validator, payload in cases:
            with self.subTest(operation=operation):
                validator.model_validate(payload)
                self.assert_error(operation, payload)

    def test_all_five_calculator_paths_equal_public_functions(self):
        arrhenius = arrhenius_input()
        # AF < 1 deliberately exercises the public warning and use-to-test life conversion.
        arrhenius["parameters"].update(test_temperature=298.15, use_temperature=343.15)
        arrhenius["life_conversion"]["input_condition"] = "use"
        fixed = fixed_input()
        fixed["time"] = 0
        fixed["parameters"]["shape"] = 0.5
        exponential, km, zero = exponential_input(), km_input(), zero_input()
        cases = [
            ("arrhenius.evaluate", arrhenius,
             V3AcceleratedSolverService().evaluate_acceleration(
                 V3AcceleratedLifeEvaluateRequest.model_validate(arrhenius))),
            ("reliability.evaluate", fixed,
             evaluate_fixed_reliability(FixedReliabilityRequest.model_validate(fixed))),
            ("reliability.evaluate", fixed_input("exponential"),
             evaluate_fixed_reliability(FixedReliabilityRequest.model_validate(fixed_input("exponential")))),
            ("exponential.fit", exponential,
             fit_exponential(ExponentialFitRequest.model_validate(exponential))),
            ("kaplan_meier.estimate", km,
             kaplan_meier(km["failures"], km["right_censored"], time_unit=km["time_unit"])),
            ("zero_failure.upper_bound", zero,
             zero_failure_upper(**zero)),
        ]
        for operation, payload, expected in cases:
            with self.subTest(operation=operation, model=payload.get("model")):
                original = deepcopy(payload)
                actual = self.assert_result(operation, payload)
                expected = json_value(expected)
                self.assertEqual(actual, expected)
                self.assertEqual(payload, original)
                for key in ("warnings", "provenance", "validation_status", "formula_validation_status",
                            "validation_scope", "limitations", "assumptions", "ffr_formal_eligibility"):
                    self.assertEqual(key in actual, key in expected)
                    if key in expected:
                        self.assertEqual(actual[key], expected[key])

    def test_exponential_observation_limit_is_inclusive(self):
        self.assertEqual(MAX_OBSERVATIONS, 10_000)
        payload = {"observations": [{"kind": "exact", "time": 1.0}
                                    for _ in range(10_000)], "time_unit": "hour"}
        result = self.assert_result("exponential.fit", payload)
        self.assertEqual(result["sample_count"], 10_000)
        payload["observations"].append({"kind": "right_censored", "time": 1.0})
        with mock.patch("app.api_v1.fit_exponential") as calculate:
            self.assert_error("exponential.fit", payload)
        calculate.assert_not_called()

    def test_kaplan_meier_limit_counts_combined_observations(self):
        for failures, censored in ((10_000, 0), (0, 10_000), (5000, 5000)):
            with self.subTest(failures=failures, censored=censored):
                payload = {"failures": [1.0] * failures, "right_censored": [2.0] * censored,
                           "time_unit": "hour"}
                self.assertEqual(self.assert_result("kaplan_meier.estimate", payload)["sample_count"], 10_000)
                payload["right_censored"].append(2.0)
                with mock.patch("app.api_v1.kaplan_meier") as calculate:
                    self.assert_error("kaplan_meier.estimate", payload)
                calculate.assert_not_called()

    def test_arrhenius_zero_energy_and_invalid_zero_domains(self):
        payload = arrhenius_input()
        payload["parameters"]["activation_energy"] = 0
        result = self.assert_result("arrhenius.evaluate", payload)
        self.assertEqual(result["acceleration_factor"], 1.0)
        self.assertEqual(result["converted_life"]["value"], 100.0)
        for path in (("parameters", "test_temperature"), ("parameters", "use_temperature"),
                     ("life_conversion", "input_life")):
            with self.subTest(path=path):
                self.assert_error("arrhenius.evaluate", replace_at(arrhenius_input(), path, 0))

    def test_fixed_weibull_zero_time_hazard_is_shape_dependent(self):
        for shape, hazard in ((0.5, None), (1, 0.001), (2, 0.0)):
            with self.subTest(shape=shape):
                payload = fixed_input()
                payload["time"] = 0
                payload["parameters"]["shape"] = shape
                result = self.assert_result("reliability.evaluate", payload)
                self.assertEqual(result["reliability"], 1.0)
                self.assertEqual(result["failure_probability"], 0.0)
                self.assertEqual(result["hazard_rate"], hazard)
                self.assertEqual(bool(result["warnings"]), shape < 1)

    def test_fixed_exponential_zero_time_and_invalid_zero_parameters(self):
        payload = fixed_input("exponential")
        payload["time"] = 0
        result = self.assert_result("reliability.evaluate", payload)
        self.assertEqual(result["reliability"], 1.0)
        self.assertEqual(result["failure_probability"], 0.0)
        self.assertEqual(result["hazard_rate"], 0.2)
        for model, parameter in (("weibull", "scale"), ("weibull", "shape"),
                                 ("exponential", "failure_rate")):
            with self.subTest(model=model, parameter=parameter):
                self.assert_error("reliability.evaluate",
                                  replace_at(fixed_input(model), ("parameters", parameter), 0))

    def test_exponential_zero_times_empty_and_all_censored_are_invalid(self):
        for index in (0, 1):
            self.assert_error("exponential.fit", replace_at(exponential_input(), ("observations", index, "time"), 0))
        for observations in ([], [{"kind": "right_censored", "time": 1.0}],
                             [{"kind": "right_censored", "time": 1.0},
                              {"kind": "right_censored", "time": 2.0}]):
            with self.subTest(observations=observations):
                self.assert_error("exponential.fit", {"observations": observations, "time_unit": "hour"})

    def test_kaplan_meier_zero_ties_all_censored_and_empty(self):
        tied = self.assert_result("kaplan_meier.estimate", {
            "failures": [0], "right_censored": [0], "time_unit": "hour"})
        self.assertEqual(tied["rows"], [{"time": 0.0, "at_risk": 2, "failures": 1,
                                        "censored_at_time": 1, "survival": 0.5}])
        terminal = self.assert_result("kaplan_meier.estimate", {
            "failures": [0], "right_censored": [], "time_unit": "hour"})
        self.assertEqual(terminal["rows"][0]["survival"], 0.0)
        censored = self.assert_result("kaplan_meier.estimate", {
            "failures": [], "right_censored": [0, 2], "time_unit": "hour"})
        self.assertEqual(censored["rows"], [])
        self.assertEqual(censored["failure_count"], 0)
        self.assertEqual(censored["last_observation_time"], 2.0)
        self.assert_error("kaplan_meier.estimate", {
            "failures": [], "right_censored": [], "time_unit": "hour"})

    def test_zero_failure_positive_sample_and_probability_boundaries(self):
        payload = zero_input()
        payload["sample_size"] = 1
        result = self.assert_result("zero_failure.upper_bound", payload)
        self.assertEqual(result["failure_count"], 0)
        self.assertEqual(result["failure_probability_upper"], 0.95)
        for key, value in (("sample_size", 0), ("sample_size", 1.0),
                           ("confidence_level", 0), ("confidence_level", 1)):
            with self.subTest(key=key, value=value):
                self.assert_error("zero_failure.upper_bound", replace_at(payload, (key,), value))

    def test_json_parser_rejects_nonfinite_literals_and_overflow_exponents(self):
        for token in (b"NaN", b"Infinity", b"-Infinity", b"1e309", b"-1e309", b"1E9999"):
            for body in (token, b'{"nested":[{"number":' + token + b"}]}"):
                with self.subTest(body=body), self.assertRaisesRegex(ValueError, "non_finite_json_number"):
                    parse_json_body(body)
        parsed = parse_json_body(b'{"finite":[1e308,-1e308,1e-309,0]}')
        self.assertEqual(parsed["finite"], [1e308, -1e308, 1e-309, 0])
        self.assertTrue(all(math.isfinite(value) for value in parsed["finite"]))

    def test_json_parser_rejects_duplicate_keys_at_any_depth(self):
        for body in (b'{"input":{"time":1,"time":2}}',
                     b'{"input":[{"time":1,"time":2}]}',
                     b'{"input":{"time":1,"\\u0074ime":2}}'):
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, "duplicate_json_key"):
                parse_json_body(body)
        self.assertEqual(parse_json_body(b'{"a":{"x":1},"b":{"x":2}}'),
                         {"a": {"x": 1}, "b": {"x": 2}})

    def test_json_body_limit_is_inclusive_and_measured_in_utf8_bytes(self):
        self.assertEqual(MAX_REQUEST_BYTES, 1_048_576)
        for encoded_char in (b"x", "é".encode("utf-8")):
            body = b'"' + encoded_char * ((MAX_REQUEST_BYTES - 2) // len(encoded_char)) + b'"'
            self.assertEqual(len(body), MAX_REQUEST_BYTES)
            value = parse_json_body(body)
            self.assertEqual(value.encode("utf-8"), body[1:-1])
            with self.assertRaisesRegex(ValueError, "request_too_large"):
                parse_json_body(body + b" ")

    def test_json_parser_requires_bytes_and_valid_utf8_and_json(self):
        for value in ('{}', bytearray(b'{}'), None):
            with self.subTest(type=type(value).__name__), self.assertRaises(TypeError):
                parse_json_body(value)
        for body in (b'"\xff"', b'"\xc3"', b'"\xed\xa0\x80"'):
            with self.subTest(body=body), self.assertRaises(UnicodeDecodeError):
                parse_json_body(body)
        for body in (b"", b'{"input":', b'{}{}'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                parse_json_body(body)
        self.assertEqual(parse_json_body('{"label":"合成"}'.encode("utf-8")), {"label": "合成"})

    def test_report_accepts_current_five_kinds_and_matches_public_renderer(self):
        records = self.saved_records()
        self.assertEqual([item["kind"] for item in records], [
            "arrhenius", "fixed_reliability", "exponential_fit", "kaplan_meier", "zero_failure_binomial"])
        for locale in ("en", "zh-CN"):
            for subset in ([record] for record in records):
                with self.subTest(locale=locale, kind=subset[0]["kind"]):
                    actual = self.assert_result("report.render_saved", {"records": subset, "locale": locale})
                    self.assertEqual(actual, render_saved_report(subset, locale=locale))
            self.assert_result("report.render_saved", {"records": records, "locale": locale})

    def test_report_accepts_zero_time_and_all_censored_km_snapshots(self):
        for failures, censored in (([0], []), ([], [0, 2])):
            with self.subTest(failures=failures, censored=censored):
                snapshot = self.assert_result("kaplan_meier.estimate", {
                    "failures": failures, "right_censored": censored, "time_unit": "hour"})
                report = self.assert_result("report.render_saved", {
                    "records": [{"kind": "kaplan_meier", "data": snapshot}]})
                parsed = ReportParser(base64.b64decode(report["content_base64"], validate=True).decode("utf-8"))
                self.assertIn(snapshot["rows"], parsed.values)

    def test_report_rejects_nelson_and_unknown_kinds_without_expanding_api(self):
        snapshot = self.saved_records()[3]["data"]
        for kind in ("nelson_aalen", "Nelson-Aalen", "SENSITIVE-KIND-MARKER"):
            with self.subTest(kind=kind):
                response = self.assert_error("report.render_saved", {"records": [{"kind": kind, "data": snapshot}]})
                self.assertNotIn("SENSITIVE-KIND-MARKER", json.dumps(response))
        response = dispatch("nelson_aalen.estimate", envelope(km_input()))
        self.assertEqual(response["error"]["code"], "unknown_operation")

    def test_saved_report_never_recalculates_writes_or_mutates_records(self):
        records = self.saved_records()
        # Valid display shapes deliberately need not match calculator arithmetic.
        records[1]["data"]["reliability"] = 0.123456789
        records[4]["data"]["failure_probability_upper"] = 0.25
        original = deepcopy(records)
        targets = [
            "app.api_v1.V3AcceleratedSolverService.evaluate_acceleration",
            "app.api_v1.evaluate_fixed_reliability", "app.api_v1.fit_exponential",
            "app.api_v1.kaplan_meier", "app.api_v1.zero_failure_upper",
            "app.services.fixed_reliability.evaluate_fixed_reliability",
            "app.services.exponential_fit.fit_exponential", "app.services.kaplan_meier.kaplan_meier",
            "app.services.zero_failure_binomial.zero_failure_upper",
            "builtins.open", "io.open", "os.open", "pathlib.Path.open",
            "pathlib.Path.write_bytes", "pathlib.Path.write_text",
        ]
        with ExitStack() as stack:
            forbidden = [stack.enter_context(mock.patch(target, side_effect=AssertionError("unexpected side effect")))
                         for target in targets]
            report = self.assert_result("report.render_saved", {"records": records})
        for patched in forbidden:
            patched.assert_not_called()
        self.assertEqual(records, original)
        parsed = ReportParser(base64.b64decode(report["content_base64"], validate=True).decode("utf-8"))
        self.assertIn(0.123456789, parsed.values)
        self.assertIn(0.25, parsed.values)
        self.assertTrue(report["presentation_only"])
        self.assertFalse(report["calculation_performed"])
        self.assertFalse(report["chart_included"])

    def test_report_asset_bytes_sha_base64_repeatability_and_escaping(self):
        records = self.saved_records()
        attack = '<svg onload="alert(1)"><script>alert(2)</script></svg>&合成'
        records[0]["data"]["warnings"] = [attack]
        records[-1]["data"]["event_definition"] = attack
        for record in records:
            record["data"]["unselected"] = "PRIVATE-ASSET-MARKER"
        for locale in ("en", "zh-CN"):
            with self.subTest(locale=locale):
                payload = {"records": records, "title": attack, "locale": locale}
                asset = self.assert_result("report.render_saved", payload)
                self.assertEqual(asset, self.assert_result("report.render_saved", payload))
                raw = base64.b64decode(asset["content_base64"], validate=True)
                self.assertEqual(base64.b64encode(raw).decode("ascii"), asset["content_base64"])
                self.assertEqual(asset["byte_size"], len(raw))
                self.assertEqual(asset["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(asset["asset_ref"], "saved-report-" + asset["sha256"][:24])
                self.assertEqual(asset["mime_type"], "text/html")
                html = raw.decode("utf-8")
                self.assertIn("&lt;svg", html)
                self.assertNotIn(attack, html)
                self.assertNotIn("PRIVATE-ASSET-MARKER", html)
                self.assertIn("default-src 'none'", html)
                parsed = ReportParser(html)
                self.assertIn(attack, parsed.values)
                self.assertIn([attack], parsed.values)
                self.assertFalse(set(parsed.tags) & {"svg", "script", "img", "iframe"})
                self.assertFalse(any(key in {"href", "src"} or key.startswith("on")
                                     for key, _ in parsed.attributes))

    def test_safe_errors_never_expose_downstream_exception_text(self):
        marker = "SENSITIVE-DOWNSTREAM-MARKER /private/synthetic/path traceback"
        cases = [
            ("arrhenius.evaluate", arrhenius_input(), "app.api_v1.V3AcceleratedSolverService.evaluate_acceleration"),
            ("reliability.evaluate", fixed_input(), "app.api_v1.evaluate_fixed_reliability"),
            ("exponential.fit", exponential_input(), "app.api_v1.fit_exponential"),
            ("kaplan_meier.estimate", km_input(), "app.api_v1.kaplan_meier"),
            ("zero_failure.upper_bound", zero_input(), "app.api_v1.zero_failure_upper"),
            ("report.render_saved", {"records": self.saved_records()}, "app.api_v1.render_saved_report"),
        ]
        for operation, payload, target in cases:
            for exception, code in ((RuntimeError, "internal_error"), (ValueError, "invalid_input"),
                                    (TypeError, "invalid_input"), (OverflowError, "invalid_input"),
                                    (NotImplementedError, "unsupported_model")):
                with self.subTest(operation=operation, exception=exception.__name__):
                    with mock.patch(target, side_effect=exception(marker)) as downstream:
                        response = self.assert_error(operation, payload, code)
                    downstream.assert_called_once()
                    encoded = json.dumps(response)
                    self.assertNotIn(marker, encoded)
                    self.assertNotIn("/private/", encoded)
                    self.assertNotIn("traceback", encoded.lower())
                    self.assertEqual(response["error"]["fields"], [])

    def test_nonfinite_downstream_result_is_not_emitted_as_json(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), mock.patch("app.api_v1.kaplan_meier", return_value={"nested": [value]}):
                self.assert_error("kaplan_meier.estimate", km_input())


if __name__ == "__main__":
    unittest.main()

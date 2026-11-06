"""Display-only contracts for frozen public synthetic survival results."""
import base64
from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

from app.services.saved_report import render_saved_report, MAX_INPUT_BYTES, _FIELD_ZH, _KIND_ZH
from app.services.v3_accelerated_solver_service import V3AcceleratedSolverService
from examples.synthetic_saved_report import main as example_main

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
FIELDS = (
    ("model", "time_unit", "sample_count", "failure_count", "right_censored_count",
     "last_observation_time", "rows", "validation_status", "limitations"),
    ("method", "failure_count", "sample_size", "confidence_level", "failure_probability_upper",
     "event_definition", "observation_window", "validation_status", "assumptions", "limitations"),
)


class ParsedReport(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.values, self.tags, self.attributes = [], [], []
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


class SavedSurvivalReportChecks(unittest.TestCase):
    def setUp(self):
        self.records = json.loads((EXAMPLES / "saved_survival_results.json").read_text(encoding="utf-8"))

    @staticmethod
    def decode(asset):
        return base64.b64decode(asset["content_base64"], validate=True).decode("utf-8")

    def test_frozen_results_are_preserved_without_any_solver(self):
        original = deepcopy(self.records)
        expected = [record["data"][field] for record, fields in zip(original, FIELDS) for field in fields]
        for locale in ("en", "zh-CN"):
            with self.subTest(locale=locale), \
                 mock.patch.object(V3AcceleratedSolverService, "evaluate_acceleration", side_effect=AssertionError("solver called")), \
                 mock.patch("app.services.fixed_reliability.evaluate_fixed_reliability", side_effect=AssertionError("solver called")), \
                 mock.patch("app.services.exponential_fit.fit_exponential", side_effect=AssertionError("solver called")), \
                 mock.patch("app.services.kaplan_meier.kaplan_meier", side_effect=AssertionError("solver called")), \
                 mock.patch("app.services.zero_failure_binomial.zero_failure_upper", side_effect=AssertionError("solver called")):
                asset = render_saved_report(self.records, locale=locale)
                self.assertEqual(ParsedReport(self.decode(asset)).values, expected)
                self.assertEqual(self.records, original)
                self.assertTrue(asset["presentation_only"])
                self.assertFalse(asset["calculation_performed"])
                self.assertFalse(asset["chart_included"])
                self.assertEqual(asset, render_saved_report(self.records, locale=locale))

    def test_statuses_are_preserved_and_cannot_be_swapped(self):
        html = self.decode(render_saved_report(self.records))
        self.assertIn('"synthetic_case_checked"', html.replace("&quot;", '"'))
        self.assertIn('"experimental_synthetic_checks_only"', html.replace("&quot;", '"'))
        for index, bad in ((0, "experimental_synthetic_checks_only"), (1, "synthetic_case_checked"), (1, "validated")):
            records = deepcopy(self.records); records[index]["data"]["validation_status"] = bad
            with self.subTest(index=index, bad=bad), self.assertRaises(ValueError):
                render_saved_report(records)

    def test_all_censored_preserves_empty_rows_and_observation_limit(self):
        record = deepcopy(self.records[0])
        record["data"].update(sample_count=2, failure_count=0, right_censored_count=2,
                              last_observation_time=3.0, rows=[])
        parsed = ParsedReport(self.decode(render_saved_report([record])))
        self.assertEqual(parsed.values, [record["data"][field] for field in FIELDS[0]])
        self.assertEqual(record["data"]["rows"], [])
        self.assertNotIn("confidence_level", self.decode(render_saved_report([record])))

    def test_zero_time_and_terminal_survival_are_supported(self):
        record = deepcopy(self.records[0])
        record["data"].update(sample_count=1, failure_count=1, right_censored_count=0,
                              last_observation_time=0.0,
                              rows=[dict(time=0.0, at_risk=1, failures=1, censored_at_time=0, survival=0.0)])
        render_saved_report([record])

    def test_malformed_kaplan_meier_values_are_rejected(self):
        changes = [("model", "Weibull"), ("time_unit", " "), ("sample_count", True),
                   ("sample_count", 5.0), ("sample_count", 0), ("sample_count", 10**400),
                   ("failure_count", -1), ("right_censored_count", False),
                   ("last_observation_time", -1), ("last_observation_time", 10**400),
                   ("last_observation_time", float("inf")), ("rows", None),
                   ("rows", []), ("limitations", []), ("limitations", [""])]
        for field, value in changes:
            record = deepcopy(self.records[0]); record["data"][field] = value
            with self.subTest(field=field, value=type(value).__name__), self.assertRaises(ValueError):
                render_saved_report([record])

    def test_malformed_kaplan_meier_rows_are_rejected(self):
        changes = [("time", True), ("time", -1), ("time", 4), ("time", 10**400),
                   ("at_risk", True), ("at_risk", 0), ("at_risk", 6),
                   ("failures", 0), ("failures", 1.0), ("failures", 6),
                   ("censored_at_time", -1), ("censored_at_time", 5),
                   ("survival", True), ("survival", -0.1), ("survival", 1.1),
                   ("survival", float("nan")), ("survival", "0.8")]
        for field, value in changes:
            record = deepcopy(self.records[0]); record["data"]["rows"][0][field] = value
            with self.subTest(field=field, value=type(value).__name__), self.assertRaises(ValueError):
                render_saved_report([record])
        for rows in ([None], [{}], list(reversed(self.records[0]["data"]["rows"]))):
            record = deepcopy(self.records[0]); record["data"]["rows"] = rows
            with self.assertRaises(ValueError):
                render_saved_report([record])

    def test_malformed_zero_failure_values_are_rejected(self):
        changes = [("method", "poisson"), ("failure_count", 1), ("failure_count", False),
                   ("sample_size", 0), ("sample_size", 1.0), ("sample_size", True),
                   ("sample_size", 10_000_001), ("confidence_level", 0), ("confidence_level", 1),
                   ("confidence_level", True), ("confidence_level", 10**400),
                   ("failure_probability_upper", 0), ("failure_probability_upper", 1.1),
                   ("failure_probability_upper", sys.float_info.min / 2),
                   ("failure_probability_upper", float("inf")), ("failure_probability_upper", True),
                   ("event_definition", ""), ("event_definition", "\u200b"),
                   ("observation_window", "x" * 501), ("observation_window", "\ud800"),
                   ("assumptions", []), ("assumptions", "text"), ("limitations", [False])]
        for field, value in changes:
            record = deepcopy(self.records[1]); record["data"][field] = value
            with self.subTest(field=field, value=type(value).__name__), self.assertRaises(ValueError):
                render_saved_report([record])

    def test_injection_and_unknown_fields_never_become_markup(self):
        text = '<img src="https://invalid.test" onerror="alert(1)"><script>alert(2)</script>&'
        records = deepcopy(self.records)
        records[0]["data"]["time_unit"] = text
        records[0]["data"]["limitations"] = [text]
        for field in ("event_definition", "observation_window"):
            records[1]["data"][field] = text
        records[1]["data"]["assumptions"] = [text]
        records[1]["data"]["limitations"] = [text]
        for record in records:
            record["data"]["unknown_field"] = "PRIVATE_SENTINEL"
        for locale in ("en", "zh-CN"):
            html = self.decode(render_saved_report(records, title=text, locale=locale))
            parsed = ParsedReport(html)
            self.assertNotIn("PRIVATE_SENTINEL", html)
            self.assertFalse(set(parsed.tags) & {"script", "img", "iframe", "svg"})
            self.assertFalse(any(k in ("src", "href") or k.startswith("on") for k, _ in parsed.attributes))
            self.assertIn(text, parsed.values)
            self.assertIn([text], parsed.values)
            self.assertIn("default-src 'none'", html)
        records[0]["data"]["rows"][0]["private_extra"] = "PRIVATE_SENTINEL"
        with self.assertRaisesRegex(ValueError, "row fields") as caught:
            render_saved_report(records)
        self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))

    def test_language_labels_cover_new_kinds_and_fields(self):
        for index, record in enumerate(self.records):
            english = self.decode(render_saved_report([record], locale="en"))
            chinese = self.decode(render_saved_report([record], locale="zh-CN"))
            self.assertIn(record["kind"], english)
            self.assertIn(_KIND_ZH[record["kind"]], chinese)
            for field in FIELDS[index]:
                self.assertIn(field, english)
                self.assertIn(_FIELD_ZH[field], chinese)

    def test_record_title_and_utf8_boundaries(self):
        render_saved_report([self.records[1]] * 25, title="t" * 160)
        for records, title in (([], "t"), ([self.records[1]] * 26, "t"),
                               (self.records, "t" * 161), (self.records, "\ud800")):
            with self.assertRaises(ValueError):
                render_saved_report(records, title=title)
        record = deepcopy(self.records[1]); record["data"]["extra"] = ""
        size = len(json.dumps([record], ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8"))
        record["data"]["extra"] = "x" * (MAX_INPUT_BYTES - size)
        render_saved_report([record])
        record["data"]["extra"] += "x"
        with self.assertRaisesRegex(ValueError, "size limit"):
            render_saved_report([record])

    def test_serialization_recursion_and_cycles_are_normalized(self):
        record = deepcopy(self.records[1])
        with mock.patch("app.services.saved_report.json.dumps", side_effect=RecursionError), self.assertRaises(ValueError):
            render_saved_report([record])
        cycle = []; cycle.append(cycle); record["data"]["unknown"] = cycle
        with self.assertRaises(ValueError):
            render_saved_report([record])

    def test_opt_in_example_reads_only_bundled_fixtures(self):
        original = json.loads((EXAMPLES / "saved_results.json").read_text(encoding="utf-8"))
        directory = Path("C:/synthetic-report-output")
        with mock.patch("sys.argv", ["example", "--output-dir", "chosen", "--include-survival"]), \
             mock.patch.object(Path, "resolve", return_value=directory), \
             mock.patch.object(Path, "is_dir", return_value=True), \
             mock.patch.object(Path, "read_text", side_effect=[json.dumps(original), json.dumps(self.records)]) as reader, \
             mock.patch.object(Path, "open", autospec=True) as opener, mock.patch("builtins.print"):
            example_main()
        self.assertEqual(reader.call_count, 2)
        opener.assert_called_once_with(directory / "reliability-report.html", "xb")
        written = opener.return_value.__enter__.return_value.write.call_args.args[0]
        self.assertIn(b"kaplan_meier", written)
        self.assertIn(b"experimental_synthetic_checks_only", written)

    def test_extended_static_demo_matches_frozen_records(self):
        original = json.loads((EXAMPLES / "saved_results.json").read_text(encoding="utf-8"))
        expected = base64.b64decode(render_saved_report(original + self.records, locale="zh-CN")["content_base64"], validate=True)
        self.assertEqual((EXAMPLES / "synthetic-survival-report.zh-CN.html").read_bytes(), expected)


if __name__ == "__main__":
    unittest.main()

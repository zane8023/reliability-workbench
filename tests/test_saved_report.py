"""Offline presentation contract using frozen synthetic result snapshots."""
import base64
from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
import unittest
from unittest import mock
from app.services.saved_report import render_saved_report, _FIELDS
from app.services.v3_accelerated_solver_service import V3AcceleratedSolverService
from app.services.fixed_reliability import evaluate_fixed_reliability
from app.services.exponential_fit import fit_exponential
from examples.synthetic_saved_report import main as report_example_main

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "saved_results.json"


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.attrs = []
        self.values = []
        self.in_pre = False
        self.buffer = ""

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(attrs)
        if tag == "pre":
            self.in_pre = True
            self.buffer = ""

    def handle_endtag(self, tag):
        if tag == "pre":
            self.values.append(json.loads(self.buffer))
            self.in_pre = False

    def handle_data(self, data):
        if self.in_pre:
            self.buffer += data


class SavedReportChecks(unittest.TestCase):
    def setUp(self):
        self.records = json.loads(FIXTURE.read_text(encoding="utf-8"))

    @staticmethod
    def decode(asset):
        return base64.b64decode(asset["content_base64"], validate=True).decode("utf-8")

    def test_preserves_all_selected_values_without_calculation(self):
        before = deepcopy(self.records)
        with mock.patch.object(V3AcceleratedSolverService, "evaluate_acceleration", side_effect=AssertionError("solver called")), \
             mock.patch("app.services.fixed_reliability.evaluate_fixed_reliability", side_effect=AssertionError("solver called")), \
             mock.patch("app.services.exponential_fit.fit_exponential", side_effect=AssertionError("solver called")):
            asset = render_saved_report(self.records, locale="zh-CN")
        parsed = ReportParser(); parsed.feed(self.decode(asset)); parsed.close()
        expected = [record["data"][field] for record in before for field in _FIELDS[record["kind"]]]
        self.assertEqual(parsed.values, expected)
        self.assertEqual(self.records, before)
        self.assertFalse(asset["calculation_performed"])
        self.assertFalse(asset["chart_included"])

    def test_bundled_static_demo_matches_rendered_fixture(self):
        expected = base64.b64decode(render_saved_report(self.records, locale="zh-CN")["content_base64"], validate=True)
        actual = (FIXTURE.parent / "synthetic-report.zh-CN.html").read_bytes()
        self.assertEqual(actual, expected)

    def test_repeatable_output_and_language(self):
        a = render_saved_report(self.records, locale="en")
        b = render_saved_report(self.records, locale="en")
        self.assertEqual(a, b)
        self.assertIn("No chart", self.decode(a))
        chinese = self.decode(render_saved_report(self.records, locale="zh-CN"))
        self.assertIn("暂不包含图表", chinese)
        self.assertIn("失效概率", chinese)
        self.assertIn("验证范围", chinese)

    def test_injection_text_is_escaped_and_no_resources(self):
        records = deepcopy(self.records)
        malicious = "<svg onload=alert(1)><script>alert(2)</script>"
        records[0]["data"]["warnings"] = [malicious]
        html = self.decode(render_saved_report(records, title=malicious))
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("<svg", html.lower())
        self.assertIn("&lt;svg", html)
        parser = ReportParser(); parser.feed(html); parser.close()
        self.assertNotIn("script", parser.tags)
        self.assertNotIn("svg", parser.tags)
        self.assertNotIn("img", parser.tags)
        self.assertFalse(any(k in ("src", "href", "onload") for k, _ in parser.attrs))
        self.assertIn("default-src 'none'", html)

    def test_missing_and_invalid_values_are_rejected(self):
        missing = deepcopy(self.records); del missing[0]["data"]["canonical_units"]
        invalid = deepcopy(self.records); invalid[1]["data"]["reliability"] = float("nan")
        bad_optional = deepcopy(self.records); bad_optional[1]["data"]["hazard_rate"] = "unknown"
        for value in (missing, invalid, bad_optional):
            with self.subTest(value=value), self.assertRaises(ValueError):
                render_saved_report(value)
        with self.assertRaises(ValueError):
            render_saved_report([])
        with self.assertRaises(ValueError):
            render_saved_report(self.records, locale="unknown")

    def test_unknown_data_not_disclosed_and_no_output_path_argument(self):
        records = deepcopy(self.records)
        records[0]["data"]["unapproved_extra"] = "PRIVATE_SENTINEL"
        html = self.decode(render_saved_report(records))
        self.assertNotIn("PRIVATE_SENTINEL", html)
        with self.assertRaises(TypeError):
            render_saved_report(records, output_path="../../escape.html")

    def test_example_writes_only_fixed_name_in_explicit_directory(self):
        directory = Path("C:/synthetic-report-output")
        with mock.patch("sys.argv", ["example", "--output-dir", "user-choice"]), \
             mock.patch.object(Path, "resolve", return_value=directory), \
             mock.patch.object(Path, "is_dir", return_value=True), \
             mock.patch.object(Path, "read_text", return_value=json.dumps(self.records)), \
             mock.patch.object(Path, "open", autospec=True) as opener, mock.patch("builtins.print"):
            report_example_main()
        opener.assert_called_once_with(directory / "reliability-report.html", "xb")
        written = opener.return_value.__enter__.return_value.write.call_args.args[0]
        self.assertIn(b"<!doctype html>", written)
        self.assertNotIn(b"<script", written.lower())

    def test_example_refuses_to_overwrite(self):
        with mock.patch("sys.argv", ["example", "--output-dir", "user-choice"]), \
             mock.patch.object(Path, "resolve", return_value=Path("C:/synthetic-report-output")), \
             mock.patch.object(Path, "is_dir", return_value=True), \
             mock.patch.object(Path, "read_text", return_value=json.dumps(self.records)), \
             mock.patch.object(Path, "open", side_effect=FileExistsError):
            with self.assertRaises(FileExistsError):
                report_example_main()

    def test_null_hazard_is_not_zero(self):
        records = deepcopy(self.records)
        records[1]["data"]["hazard_rate"] = None
        parsed = ReportParser(); parsed.feed(self.decode(render_saved_report(records))); parsed.close()
        self.assertIn(None, parsed.values)


if __name__ == "__main__":
    unittest.main()

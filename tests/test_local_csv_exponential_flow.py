import base64
import hashlib
import importlib
import json
import math
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

import local_csv_exponential_flow as flow


class LocalCsvExponentialFlowTests(unittest.TestCase):
    RAW = b"kind,time\nexact,1\nexact,2\nexact,3\nright_censored,4\nright_censored,5\n"

    def test_success_is_real_calculation_and_bilingual_summary(self):
        for locale, scale_label in (("en", "scale"), ("zh-CN", "寿命尺度")):
            with self.subTest(locale=locale):
                output = flow.analyze_csv(self.RAW, "hour", locale)
                self.assertTrue(output["ok"])
                self.assertEqual(output["result"]["sample_count"], 5)
                self.assertEqual(output["result"]["failure_count"], 3)
                self.assertEqual(output["result"]["right_censored_count"], 2)
                self.assertEqual(output["result"]["total_exposure"], 15.0)
                self.assertEqual(output["result"]["scale"], 5.0)
                self.assertEqual(output["result"]["time_unit"], "hour")
                self.assertIn("provenance", output["result"])
                html = base64.b64decode(output["report"]["content_base64"], validate=True)
                self.assertEqual(output["report"]["sha256"], hashlib.sha256(html).hexdigest())
                self.assertIn(("<th>" + scale_label + "</th><td><pre>5.0</pre></td></tr>").encode("utf-8"), html)
                self.assertFalse(output["report"]["calculation_performed"])
                json.dumps(output, allow_nan=False)

    def test_input_is_unchanged_and_output_repeatable(self):
        before = self.RAW[:]
        self.assertEqual(flow.analyze_csv(self.RAW, "hour", "en"), flow.analyze_csv(self.RAW, "hour", "en"))
        self.assertEqual(self.RAW, before)

    def test_one_fit_and_no_common_io_calls(self):
        with patch.object(flow, "fit_exponential", wraps=flow.fit_exponential) as fit, \
             patch.object(Path, "open", side_effect=AssertionError("file open")), \
             patch("builtins.open", side_effect=AssertionError("file open")), \
             patch.object(socket.socket, "connect", side_effect=AssertionError("network connect")):
            answer = flow.analyze_csv(self.RAW, "hour", "en")
        self.assertTrue(answer["ok"])
        self.assertEqual(fit.call_count, 1)

    def test_all_censored_stops_before_fit(self):
        with patch.object(flow, "fit_exponential", side_effect=AssertionError("must not fit")):
            answer = flow.analyze_csv(b"kind,time\nright_censored,1\nright_censored,2\n", "hour", "en")
        self.assertEqual(answer, {"ok": False, "error": {"code": "NO_OBSERVED_FAILURES"}})

    def test_invalid_requests_are_safe_and_do_not_fit(self):
        cases = ((b"kind,time\nprivate_sentinel,1\n", "hour", "en", "INVALID_EVENT_KIND"),
                 (b"kind,kind\nexact,1\n", "hour", "en", "DUPLICATE_HEADER"),
                 (b"kind,time\nexact,1\n", "century", "en", "INVALID_TIME_UNIT"),
                 (self.RAW, "hour", "fr", "INVALID_LOCALE"),
                 (b"kind,time\nexact,0\n", "hour", "en", "INVALID_TIME"),
                 (b"\xff", "hour", "en", "INVALID_ENCODING"))
        for raw, unit, locale, expected in cases:
            with self.subTest(expected=expected), patch.object(flow, "fit_exponential", side_effect=AssertionError("must not fit")):
                answer = flow.analyze_csv(raw, unit, locale)
                self.assertEqual(answer["error"]["code"], expected)
                self.assertNotIn("private_sentinel", json.dumps(answer))

    def test_float_rounding_is_visible(self):
        raw = b"kind,time\nexact,9007199254740991.5\n"
        answer = flow.analyze_csv(raw, "hour", "en")
        self.assertTrue(answer["ok"])
        self.assertEqual(answer["normalized_request"]["observations"][0]["time"], float(2**53))
        self.assertTrue(any("rounded" in item for item in answer["limitations"]))
        rejected = flow.analyze_csv(b"kind,time\nexact,9007199254740993\n", "hour", "en")
        self.assertEqual(rejected["error"]["code"], "INVALID_TIME")

    def test_estimator_warning_and_math(self):
        answer = flow.analyze_csv(b"kind,time\nexact,2\nright_censored,3\n", "hour", "en")
        self.assertTrue(answer["ok"])
        self.assertEqual(answer["result"]["scale"], 5.0)
        self.assertTrue(any("precision" in warning.lower() for warning in answer["result"]["warnings"]))
        self.assertTrue(math.isfinite(answer["result"]["failure_rate"]))

    def test_unexpected_error_does_not_echo_details(self):
        with patch.object(flow, "fit_exponential", side_effect=RuntimeError("private_sentinel")):
            answer = flow.analyze_csv(self.RAW, "hour", "en")
        self.assertEqual(answer["error"]["code"], "INTERNAL_ERROR")
        self.assertNotIn("private_sentinel", json.dumps(answer))

    def test_fit_and_report_errors_do_not_echo_details(self):
        for target in ("fit_exponential", "render_saved_report"):
            for error_type in (ValueError, TypeError, OverflowError):
                with self.subTest(target=target, error=error_type.__name__):
                    with patch.object(flow, target, side_effect=error_type("private_sentinel")):
                        answer = flow.analyze_csv(self.RAW, "hour", "en")
                    self.assertEqual(answer, {"ok": False, "error": {"code": "FIT_OR_REPORT_FAILED"}})

    def test_nonrepresentable_subnormal_fit_fails_safely(self):
        raw = b"kind,time\nexact,5e-324\n"
        self.assertTrue(flow.parse_observations(raw, "hour")["ok"])
        self.assertEqual(flow.analyze_csv(raw, "hour", "en"),
                         {"ok": False, "error": {"code": "FIT_OR_REPORT_FAILED"}})

    def test_memory_error_propagates(self):
        for target in ("fit_exponential", "render_saved_report"):
            with self.subTest(target=target):
                with patch.object(flow, target, side_effect=MemoryError("private_sentinel")):
                    with self.assertRaises(MemoryError):
                        flow.analyze_csv(self.RAW, "hour", "en")

    def test_test_environment_uses_published_modules(self):
        # Reviewed integration baseline: c2a0101ec3961f863e0189afd4aaecb1bc5d775e.
        # The original e353434 candidate and its identity evidence are retained
        # separately; these pins must track a deliberately reviewed source update.
        root = Path(flow.__file__).resolve().parent
        for module_name, relative, expected in (
            ("app.services.exponential_fit", "app/services/exponential_fit.py", "d866b663106eeecb63a82ebe2b782792a0e308b076156e54390609e105a55420"),
            ("app.validators.exponential_fit", "app/validators/exponential_fit.py", "9e4a3744ed9cde0ae38b9a891e3e0918784902f89b10c76141d55edd11717f0f"),
            ("app.services.saved_report", "app/services/saved_report.py", "86dd1b22dd1edc568f5b6b9ab7d12119fcfde60596ff8b564c6ff7b814dd4aad")):
            path = Path(importlib.import_module(module_name).__file__).resolve()
            self.assertEqual(path, (root / relative).resolve())
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()

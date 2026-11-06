import base64
import json
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.exponential_fit import fit_exponential
from app.services.saved_report import render_saved_report
from app.validators.exponential_fit import ExponentialFitRequest
import local_lifetime_csv_candidate as candidate


class LifetimeCsvCandidateTests(unittest.TestCase):
    def test_synthetic_fit_and_report(self):
        raw = b"kind,time\nexact,1\nexact,2\nexact,3\nright_censored,4\nright_censored,5\n"
        with patch.object(Path, "open", side_effect=AssertionError("file access")), \
             patch("builtins.open", side_effect=AssertionError("file access")), \
             patch.object(socket.socket, "connect", side_effect=AssertionError("network")):
            parsed = candidate.parse_observations(raw, "hour")
            self.assertTrue(parsed["ok"])
            request = ExponentialFitRequest.model_validate(parsed["request"], strict=True)
            result = fit_exponential(request).model_dump(mode="json")
            with patch("app.services.exponential_fit.fit_exponential", side_effect=AssertionError("report recalculated")):
                report = render_saved_report([{"kind": "exponential_fit", "data": result}], locale="en")
        self.assertEqual(result["failure_count"], 3)
        self.assertEqual(result["right_censored_count"], 2)
        self.assertEqual(result["total_exposure"], 15.0)
        self.assertEqual(result["scale"], 5.0)
        self.assertIn(b'<th>scale</th><td><pre>5.0</pre></td></tr>', base64.b64decode(report["content_base64"], validate=True))
        self.assertFalse(report["calculation_performed"])
        self.assertEqual(parsed, candidate.parse_observations(raw, "hour"))
        self.assertEqual(raw, b"kind,time\nexact,1\nexact,2\nexact,3\nright_censored,4\nright_censored,5\n")

    def test_utf8_bom_and_crlf(self):
        parsed = candidate.parse_observations(b'\xef\xbb\xbfkind,time\r\n"exact","1.5"\r\nright_censored,2e0\r\n', "day")
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["request"]["observations"], [{"kind": "exact", "time": 1.5}, {"kind": "right_censored", "time": 2.0}])
        self.assertEqual(parsed["request"]["time_unit"], "day")

    def test_quoted_newlines_are_not_silently_removed(self):
        for raw, code in ((b'kind,time\n"ex\nact",1\n', "INVALID_EVENT_KIND"),
                          (b'kind,time\nexact,"1\n2"\n', "INVALID_TIME")):
            with self.subTest(raw=raw):
                error = candidate.parse_observations(raw, "hour")["error"]
                self.assertEqual(error["code"], code)
                self.assertEqual(error["line"], 3)

    def test_duplicate_missing_or_unknown_header(self):
        for raw, code in ((b"kind,kind\nexact,1\n", "DUPLICATE_HEADER"),
                          (b"time,kind\n1,exact\n", "INVALID_HEADER"),
                          (b"kind,time,private\nexact,1,x\n", "INVALID_HEADER"),
                          (b"kind,\nexact,1\n", "INVALID_HEADER")):
            with self.subTest(raw=raw):
                self.assertEqual(candidate.parse_observations(raw, "hour")["error"]["code"], code)

    def test_invalid_rows_and_csv(self):
        cases = ((b"kind,time\nexact\n", "INVALID_ROW_WIDTH"),
                 (b"kind,time\nexact,1,extra\n", "INVALID_ROW_WIDTH"),
                 (b'kind,time\n"unterminated,1\n', "INVALID_CSV"),
                 (b"kind,time\nunknown,1\n", "INVALID_EVENT_KIND"),
                 (b"kind,time\nexact,1\n\n", "INVALID_ROW_WIDTH"),
                 (b"kind,time\n", "NO_OBSERVATIONS"))
        for raw, code in cases:
            with self.subTest(raw=raw):
                self.assertEqual(candidate.parse_observations(raw, "hour")["error"]["code"], code)

    def test_times_and_units(self):
        for token in (b"0", b"-1", b"NaN", b"inf", b"1e999", b"1e-9999", b"9007199254740993", b" 1", b"1 "):
            with self.subTest(token=token):
                self.assertEqual(candidate.parse_observations(b"kind,time\nexact," + token + b"\n", "hour")["error"]["code"], "INVALID_TIME")
        self.assertEqual(candidate.parse_observations(b"kind,time\nexact,1\n", "century")["error"]["code"], "INVALID_TIME_UNIT")
        self.assertEqual(candidate.parse_observations(b"kind,time\nexact,1\n", None)["error"]["code"], "INVALID_TIME_UNIT")

    def test_documented_numeric_syntax_and_units(self):
        tokens = ((b"1", 1.0), (b"+1.5", 1.5), (b".5", 0.5),
                  (b"1.", 1.0), (b"2e0", 2.0), (b"2E+0", 2.0))
        for unit in candidate.UNITS:
            for token, expected in tokens:
                with self.subTest(unit=unit, token=token):
                    answer = candidate.parse_observations(b"kind,time\nexact," + token + b"\n", unit)
                    self.assertTrue(answer["ok"])
                    self.assertEqual(answer["request"]["time_unit"], unit)
                    self.assertEqual(answer["request"]["observations"][0]["time"], expected)
        self.assertEqual(candidate.parse_observations(b"kind,time\nexact,1_000\n", "hour"),
                         {"ok": False, "error": {"code": "INVALID_TIME", "line": 2}})

    def test_bounds(self):
        self.assertEqual(candidate.parse_observations("x", "hour")["error"]["code"], "INVALID_INPUT_SIZE_OR_TYPE")
        self.assertEqual(candidate.parse_observations(b"", "hour")["error"]["code"], "INVALID_INPUT_SIZE_OR_TYPE")
        self.assertEqual(candidate.parse_observations(b"x" * (candidate.MAX_BYTES + 1), "hour")["error"]["code"], "INVALID_INPUT_SIZE_OR_TYPE")
        self.assertNotEqual(candidate.parse_observations(b"x" * candidate.MAX_BYTES, "hour")["error"]["code"], "INVALID_INPUT_SIZE_OR_TYPE")
        self.assertTrue(candidate.parse_observations(b"kind,time\n" + b"exact,1\n" * candidate.MAX_ROWS, "hour")["ok"])
        self.assertEqual(candidate.parse_observations(b"kind,time\n" + b"exact,1\n" * (candidate.MAX_ROWS + 1), "hour")["error"]["code"], "ROW_LIMIT_EXCEEDED")
        self.assertEqual(candidate.parse_observations(b"kind,time\nexact," + b"1" * (candidate.MAX_CELL + 1) + b"\n", "hour")["error"]["code"], "CELL_LIMIT_EXCEEDED")

    def test_encoding_null_and_error_privacy(self):
        self.assertEqual(candidate.parse_observations(b"\xff", "hour")["error"]["code"], "INVALID_ENCODING")
        self.assertEqual(candidate.parse_observations(b"kind,time\nexact,\x00\n", "hour")["error"]["code"], "INVALID_TEXT")
        answer = candidate.parse_observations(b"kind,time\nprivate_sentinel,1\n", "hour")
        self.assertNotIn("private_sentinel", json.dumps(answer))

    def test_all_censored_is_not_a_fitted_lifetime(self):
        parsed = candidate.parse_observations(b"kind,time\nright_censored,1\nright_censored,2\n", "hour")
        self.assertTrue(parsed["ok"])
        with self.assertRaises(ValueError):
            fit_exponential(ExponentialFitRequest.model_validate(parsed["request"], strict=True))

    def test_memory_error_propagates(self):
        with patch.object(candidate, "Decimal", side_effect=MemoryError("private_sentinel")):
            with self.assertRaises(MemoryError):
                candidate.parse_observations(b"kind,time\nexact,1\n", "hour")


if __name__ == "__main__":
    unittest.main()

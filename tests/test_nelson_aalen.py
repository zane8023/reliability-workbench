import hashlib
import importlib
import json
import math
from fractions import Fraction
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from app.services import nelson_aalen as candidate


class NelsonAalenCandidateTests(unittest.TestCase):
    def test_censor_tied_with_failure(self):
        answer = candidate.nelson_aalen_point([1, 2], [2, 3], time_unit="hour")
        self.assertEqual([(r["at_risk"], r["failures"], r["censored_at_time"]) for r in answer["rows"]], [(4, 1, 0), (3, 1, 1)])
        self.assertAlmostEqual(answer["rows"][-1]["cumulative_hazard"], float(Fraction(7, 12)), places=15)
        self.assertEqual(answer["last_observation_time"], 3.0)

    def test_multiple_ties_against_fraction(self):
        answer = candidate.nelson_aalen_point([1, 1, 2], [2, 3], time_unit="day")
        self.assertAlmostEqual(answer["rows"][-1]["cumulative_hazard"], float(Fraction(11, 15)), places=15)
        self.assertEqual(answer["rows"][0]["failures"], 2)
        self.assertEqual(answer["time_unit"], "day")

    def test_censor_before_last_failure(self):
        answer = candidate.nelson_aalen_point([1, 2, 4], [3], time_unit="hour")
        self.assertAlmostEqual(answer["rows"][-1]["cumulative_hazard"], float(Fraction(19, 12)), places=15)

    def test_all_fail_together_is_not_km_survival(self):
        answer = candidate.nelson_aalen_point([1, 1, 1, 1], time_unit="hour")
        self.assertEqual(answer["rows"][-1]["cumulative_hazard"], 1.0)
        self.assertNotIn("survival", answer["rows"][-1])
        self.assertTrue(any("not a Kaplan-Meier" in text for text in answer["limitations"]))

    def test_km_survival_values_are_not_used_as_hazard(self):
        original = candidate.kaplan_meier
        def modified(*args, **kwargs):
            data = original(*args, **kwargs)
            for row in data["rows"]:
                row["survival"] = float("nan")
            return data
        with patch.object(candidate, "kaplan_meier", side_effect=modified):
            answer = candidate.nelson_aalen_point([1, 2], [2, 3], time_unit="hour")
        self.assertAlmostEqual(answer["rows"][-1]["cumulative_hazard"], float(Fraction(7, 12)), places=15)
        json.dumps(answer, allow_nan=False)

    def test_no_failure_and_empty_are_quality_gate(self):
        for failures, censored in (([], []), ([], [1, 2])):
            with self.subTest(censored=censored), self.assertRaisesRegex(ValueError, "at least one"):
                candidate.nelson_aalen_point(failures, censored, time_unit="hour")

    def test_invalid_values_and_preview_zero_gate(self):
        for value in (0, -1, True, float("nan"), float("inf"), -float("inf"), "1", 2**53 + 1, 10**400):
            with self.subTest(value=str(value)[:30]), self.assertRaises(ValueError):
                candidate.nelson_aalen_point([value], time_unit="hour")
        with self.assertRaises(ValueError):
            candidate.nelson_aalen_point([1], [0], time_unit="hour")

    def test_observation_and_unit_contract(self):
        for failures, censored, unit in (([1], (), "century"), ([1], (), None), ((1,), None, "hour"), (iter([1]), (), "hour")):
            with self.subTest(unit=unit), self.assertRaises(ValueError):
                candidate.nelson_aalen_point(failures, censored, time_unit=unit)
        with self.assertRaisesRegex(ValueError, "limit"):
            candidate.nelson_aalen_point([1] * (candidate.MAX_OBSERVATIONS + 1), time_unit="hour")
        maximum = candidate.nelson_aalen_point([1] * candidate.MAX_OBSERVATIONS, time_unit="hour")
        self.assertEqual(maximum["rows"][0]["at_risk"], candidate.MAX_OBSERVATIONS)
        self.assertEqual(maximum["rows"][0]["cumulative_hazard"], 1.0)

    def test_unit_scaling_changes_times_not_risks(self):
        hours = candidate.nelson_aalen_point([1, 2], [2, 3], time_unit="hour")
        minutes = candidate.nelson_aalen_point([60, 120], [120, 180], time_unit="minute")
        for left, right in zip(hours["rows"], minutes["rows"]):
            self.assertEqual(right["time"], 60 * left["time"])
            self.assertEqual(right["at_risk"], left["at_risk"])
            self.assertEqual(right["cumulative_hazard"], left["cumulative_hazard"])

    def test_valid_extreme_and_float_rounding_limit(self):
        answer = candidate.nelson_aalen_point([5e-324, 2**53 + 2], time_unit="second")
        self.assertEqual(answer["rows"][0]["time"], 5e-324)
        self.assertEqual(answer["rows"][-1]["time"], float(2**53 + 2))
        rounded = candidate.nelson_aalen_point([9007199254740993.0], time_unit="second")
        self.assertEqual(rounded["rows"][0]["time"], float(2**53))
        self.assertTrue(any("rounded" in text for text in rounded["limitations"]))

    def test_neighboring_float_times_remain_distinct(self):
        later = math.nextafter(1.0, math.inf)
        after_censoring = candidate.nelson_aalen_point([later], [1.0], time_unit="hour")
        self.assertEqual(after_censoring["rows"][0]["at_risk"], 1)
        self.assertEqual(after_censoring["rows"][0]["cumulative_hazard"], 1.0)
        before_censoring = candidate.nelson_aalen_point([1.0], [later], time_unit="hour")
        self.assertEqual(before_censoring["rows"][0]["at_risk"], 2)
        self.assertEqual(before_censoring["rows"][0]["cumulative_hazard"], 0.5)

    def test_order_repeatability_and_input_unchanged(self):
        failures, censored = [4, 1, 2], [3, 2]
        before = failures[:], censored[:]
        a = candidate.nelson_aalen_point(failures, censored, time_unit="hour")
        b = candidate.nelson_aalen_point(list(reversed(failures)), list(reversed(censored)), time_unit="hour")
        self.assertEqual(a, b)
        self.assertEqual((failures, censored), before)
        self.assertEqual(json.loads(json.dumps(a, allow_nan=False)), a)

    def test_compensated_sum_against_fraction_reference(self):
        n = 2000
        answer = candidate.nelson_aalen_point(list(range(1, n + 1)), time_unit="hour")
        reference = float(sum((Fraction(1, k) for k in range(1, n + 1)), Fraction(0)))
        self.assertAlmostEqual(answer["rows"][-1]["cumulative_hazard"], reference, places=14)
        self.assertTrue(all(a["cumulative_hazard"] <= b["cumulative_hazard"] for a, b in zip(answer["rows"], answer["rows"][1:])))

    def test_no_common_io_calls_during_calculation(self):
        with patch.object(Path, "open", side_effect=AssertionError("file open")), \
             patch("builtins.open", side_effect=AssertionError("file open")), \
             patch.object(socket.socket, "connect", side_effect=AssertionError("network connect")):
            result = candidate.nelson_aalen_point([1, 2], [2, 3], time_unit="hour")
        self.assertEqual(result["validation_status"], "synthetic_case_checked")

    def test_risk_module_matches_published_baseline(self):
        root = Path(candidate.__file__).resolve().parents[2]
        path = Path(importlib.import_module("app.services.kaplan_meier").__file__).resolve()
        self.assertEqual(path, (root / "app/services/kaplan_meier.py").resolve())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), "6841155df35b49c16cceb3befe79de64fe5fbc3c5550e9f24725cbc482406aaf")


if __name__ == "__main__":
    unittest.main()

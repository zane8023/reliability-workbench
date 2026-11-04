import json
import unittest
from app.services.kaplan_meier import kaplan_meier


class KaplanMeierChecks(unittest.TestCase):
    def test_hand_calculated_ties_and_censoring(self):
        r = kaplan_meier([1, 2, 2], [2, 3], time_unit="hour")
        self.assertEqual([(x["at_risk"], x["failures"]) for x in r["rows"]], [(5, 1), (4, 2)])
        self.assertAlmostEqual(r["rows"][0]["survival"], .8)
        self.assertAlmostEqual(r["rows"][1]["survival"], .4)
        self.assertEqual(r["rows"][1]["censored_at_time"], 1)
    def test_censor_before_failure_and_units(self):
        a = kaplan_meier([2, 4], [1, 2, 5], time_unit="hour")
        self.assertEqual([(r["at_risk"], r["failures"], r["censored_at_time"]) for r in a["rows"]], [(4, 1, 1), (2, 1, 0)])
        self.assertAlmostEqual(a["rows"][0]["survival"], .75)
        self.assertAlmostEqual(a["rows"][1]["survival"], .375)
        b = kaplan_meier([120, 240], [60, 120, 300], time_unit="minute")
        self.assertEqual([r["survival"] for r in a["rows"]], [r["survival"] for r in b["rows"]])
    def test_follow_up_and_unrepresentable_integer(self):
        r = kaplan_meier([], [1, 3], time_unit="h")
        self.assertEqual((r["failure_count"], r["right_censored_count"], r["last_observation_time"]), (0, 2, 3))
        with self.assertRaises(ValueError):
            kaplan_meier([2**53], [2**53 + 1], time_unit="h")
    def test_all_fail_together(self):
        r = kaplan_meier([1, 1], [], time_unit="h")
        self.assertEqual(r["rows"][0]["survival"], 0.0)
    def test_only_censored_and_zero_time(self):
        self.assertEqual(kaplan_meier([], [0, 1], time_unit="h")["rows"], [])
        self.assertEqual(kaplan_meier([0], [], time_unit="h")["rows"][0]["survival"], 0)
    def test_order_and_json(self):
        a = kaplan_meier([2, 1, 2], [3, 2], time_unit="h")
        b = kaplan_meier([1, 2, 2], [2, 3], time_unit="h")
        self.assertEqual(a, b)
        json.dumps(a, allow_nan=False)
    def test_invalid(self):
        for bad in (float("nan"), float("inf"), -1, True, "1", 10**400):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                kaplan_meier([bad], [], time_unit="h")
        for failures, censored, unit in (([], [], "h"), ([1], [], ""), (None, [], "h")):
            with self.assertRaises(ValueError):
                kaplan_meier(failures, censored, time_unit=unit)

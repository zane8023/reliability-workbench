"""Independent synthetic checks for exact/right-censored exponential MLE."""
import json
import math
import unittest
from decimal import Decimal, localcontext
from pydantic import ValidationError
from app.validators.exponential_fit import ExponentialFitRequest, ExponentialFitResult, ExponentialObservation
from app.services.exponential_fit import fit_exponential


class ExponentialFitChecks(unittest.TestCase):
    def fit(self, values, unit="hour"):
        return fit_exponential(ExponentialFitRequest(time_unit=unit, observations=[
            {"kind": kind, "time": time} for kind, time in values]))

    def test_closed_form_right_censoring(self):
        result = self.fit([("exact", 1), ("exact", 2), ("exact", 3),
                           ("right_censored", 4), ("right_censored", 5)])
        self.assertEqual((result.sample_count, result.failure_count, result.right_censored_count), (5, 3, 2))
        self.assertEqual(result.total_exposure, 15)
        self.assertEqual(result.scale, 5)
        self.assertTrue(math.isclose(result.failure_rate, 0.2, rel_tol=1e-15))
        self.assertTrue(any("Fewer than five" in w for w in result.warnings))

    def test_complete_failures(self):
        r = self.fit([("exact", x) for x in (1, 2, 3, 4)])
        self.assertEqual(r.scale, 2.5)
        self.assertEqual(r.failure_rate, 0.4)

    def test_one_failure_is_computable_with_warning(self):
        r = self.fit([("exact", 1), ("right_censored", 4)])
        self.assertEqual(r.failure_count, 1)
        self.assertEqual(r.scale, 5)
        self.assertTrue(any("Fewer than five" in w for w in r.warnings))

    def test_zero_failure_refuses_positive_point_mle(self):
        with self.assertRaisesRegex(ValueError, "not identifiable"):
            self.fit([("right_censored", 1), ("right_censored", 4)])

    def test_order_and_repeatability(self):
        values = [("exact", 1), ("exact", 2), ("exact", 3), ("right_censored", 4)]
        a, b = self.fit(values), self.fit(list(reversed(values)))
        self.assertEqual(a.model_dump(mode="json"), b.model_dump(mode="json"))
        self.assertEqual(a.model_dump(mode="json"), self.fit(values).model_dump(mode="json"))

    def test_unit_scale_equivariance(self):
        h = self.fit([("exact", 24), ("exact", 48), ("right_censored", 72)])
        d = self.fit([("exact", 1), ("exact", 2), ("right_censored", 3)], "day")
        self.assertTrue(math.isclose(h.scale / 24, d.scale, rel_tol=1e-15))
        self.assertTrue(math.isclose(h.failure_rate * 24, d.failure_rate, rel_tol=1e-15))
        self.assertEqual(d.failure_rate_unit, "1/day")

    def test_extreme_large_total_without_nonfinite_json(self):
        r = self.fit([("exact", 1e308)] * 3)
        self.assertIsNone(r.total_exposure)
        self.assertTrue(math.isclose(r.scale, 1e308, rel_tol=1e-15))
        self.assertTrue(math.isclose(r.failure_rate, 1e-308, rel_tol=1e-15))
        self.assertTrue(any("scaled representation" in w for w in r.warnings))
        json.dumps(r.model_dump(mode="json"), allow_nan=False)

    def test_small_times_against_decimal(self):
        values = [("exact", 1e-308), ("exact", 2e-308), ("right_censored", 3e-308)]
        with localcontext() as ctx:
            ctx.prec = 100
            total = sum((Decimal.from_float(time) for _, time in values), Decimal(0))
            expected_scale = float(total / 2)
            expected_rate = float(Decimal(2) / total)
        r = self.fit(values)
        self.assertTrue(math.isclose(r.scale, expected_scale, rel_tol=1e-14))
        self.assertTrue(math.isclose(r.failure_rate, expected_rate, rel_tol=1e-14))

    def test_nonrepresentable_estimate_rejected(self):
        with self.assertRaisesRegex(ValueError, "floating-point range"):
            self.fit([("exact", 5e-324)])

    def test_invalid_and_unsupported_input(self):
        cases = [dict(time_unit="hour", observations=[]),
                 dict(time_unit="hour", observations=[dict(kind="exact", time=0)]),
                 dict(time_unit="hour", observations=[dict(kind="exact", time=float("inf"))]),
                 dict(time_unit="hour", observations=[dict(kind="exact", time=float("nan"))]),
                 dict(time_unit="hour", observations=[dict(kind="left_censored", time=1)]),
                 dict(time_unit="hour", observations=[dict(kind="interval_censored", lower=1, upper=2)]),
                 dict(time_unit="hour", observations=[dict(kind="exact", time=1, entry_time=0.2)]),
                 dict(time_unit="hour", observations=[dict(kind="exact", time=1, count=3)]),
                 dict(time_unit="hour", observations=[dict(kind="exact", time=1)], uq={}),
                 dict(time_unit="bad", observations=[dict(kind="exact", time=1)])]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValidationError):
                ExponentialFitRequest(**case)

    def test_unvalidated_constructed_input_rejected(self):
        bad = ExponentialFitRequest.model_construct(time_unit="hour", observations=[
            ExponentialObservation.model_construct(kind="exact", time=-1)])
        with self.assertRaises(ValidationError):
            fit_exponential(bad)

    def test_json_contract_and_scope(self):
        r = self.fit([("exact", 1), ("exact", 2), ("exact", 3)])
        payload = json.loads(r.model_dump_json())
        self.assertEqual(ExponentialFitResult.model_validate(payload), r)
        json.dumps(payload, allow_nan=False)
        self.assertEqual(payload["validation_status"], "synthetic_case_checked")
        self.assertNotIn("confidence_interval", payload)
        self.assertIn("not model or field validation", payload["validation_scope"])


if __name__ == "__main__":
    unittest.main()

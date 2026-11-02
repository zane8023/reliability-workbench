"""Synthetic closed-form and contract checks; no field validation."""
import json
import math
import unittest
from decimal import Decimal, localcontext
from pydantic import ValidationError
from app.validators.fixed_reliability import FixedReliabilityRequest, FixedReliabilityResult
from app.services.fixed_reliability import evaluate_fixed_reliability


class FixedReliabilityChecks(unittest.TestCase):
    def evaluate(self, model="weibull", params=None, time=100.0, unit="hour", probability=0.1):
        if params is None:
            params = {"scale": 1000.0, "shape": 2.0}
        request = FixedReliabilityRequest(model=model, parameters=params, time=time,
                                          time_unit=unit, quantile_probability=probability)
        return evaluate_fixed_reliability(request)

    def test_weibull_reference(self):
        r = self.evaluate()
        self.assertAlmostEqual(r.reliability, math.exp(-0.01), places=14)
        self.assertAlmostEqual(r.failure_probability, -math.expm1(-0.01), places=15)
        self.assertAlmostEqual(r.hazard_rate, 0.0002, places=15)
        self.assertAlmostEqual(r.quantile_time, 1000 * math.sqrt(-math.log(0.9)), places=10)

    def test_exponential_reference(self):
        r = self.evaluate("exponential", {"failure_rate": 0.002}, 100.0)
        self.assertAlmostEqual(r.reliability, math.exp(-0.2), places=14)
        self.assertAlmostEqual(r.failure_probability, -math.expm1(-0.2), places=14)
        self.assertEqual(r.hazard_rate, 0.002)
        self.assertAlmostEqual(r.quantile_time, -math.log(0.9) / 0.002, places=10)

    def test_weibull_zero_hazard_cases(self):
        for shape, expected in [(0.5, None), (1.0, 0.001), (2.0, 0.0)]:
            with self.subTest(shape=shape):
                r = self.evaluate(params={"scale": 1000.0, "shape": shape}, time=0)
                self.assertEqual((r.reliability, r.failure_probability), (1.0, 0.0))
                self.assertEqual(r.hazard_rate, expected)
                self.assertEqual(bool(r.warnings), shape < 1)

    def test_small_probability_stability(self):
        r = self.evaluate("exponential", {"failure_rate": 1e-20}, 1.0, probability=1e-12)
        self.assertGreater(r.failure_probability, 0)
        self.assertTrue(math.isclose(r.failure_probability, 1e-20, rel_tol=1e-14))
        self.assertTrue(math.isclose(r.quantile_time, -math.log1p(-1e-12)/1e-20, rel_tol=1e-14))

    def test_large_exposure_saturates_probabilities(self):
        r = self.evaluate("exponential", {"failure_rate": 1.0}, 1000.0)
        self.assertEqual((r.reliability, r.failure_probability), (0.0, 1.0))

    def test_units_and_equivalent_scales(self):
        h = self.evaluate(params={"scale": 240.0, "shape": 2.0}, time=24, unit="hour")
        d = self.evaluate(params={"scale": 10.0, "shape": 2.0}, time=1, unit="day")
        self.assertTrue(math.isclose(h.reliability, d.reliability, rel_tol=1e-14))
        self.assertTrue(math.isclose(h.quantile_time / 24, d.quantile_time, rel_tol=1e-14))
        self.assertTrue(math.isclose(h.hazard_rate * 24, d.hazard_rate, rel_tol=1e-14))
        self.assertEqual(d.hazard_unit, "1/day")

    def test_invalid_parameters_and_inputs(self):
        cases = [dict(model="weibull",parameters={"scale": 0,"shape": 1},time=0,time_unit="hour"),
                 dict(model="weibull",parameters={"scale": 1},time=0,time_unit="hour"),
                 dict(model="exponential",parameters={"failure_rate": float("nan")},time=0,time_unit="hour"),
                 dict(model="exponential",parameters={"failure_rate": 1},time=float("inf"),time_unit="hour"),
                 dict(model="exponential",parameters={"failure_rate": 1},time=-1,time_unit="hour"),
                 dict(model="exponential",parameters={"failure_rate": 1},time=0,time_unit="hour",quantile_probability=1),
                 dict(model="exponential",parameters={"failure_rate": 1},time=0,time_unit="invalid")]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValidationError):
                FixedReliabilityRequest(**case)

    def test_rejects_nonrepresentable_quantile(self):
        with self.assertRaises(ValueError):
            self.evaluate("exponential", {"failure_rate": 5e-324}, 0.0, probability=0.5)
        with self.assertRaises(ValueError):
            self.evaluate("weibull", {"scale": 5e-324, "shape": 2.0}, 0.0)

    def test_near_equal_large_values_against_decimal(self):
        scale = 1e100
        shape = 1e16
        for time in (math.nextafter(scale, 0.0), scale, math.nextafter(scale, math.inf)):
            with self.subTest(time=time), localcontext() as ctx:
                ctx.prec = 100
                dt, ds, dk = map(Decimal.from_float, (time, scale, shape))
                expected = float((-(dk * (dt / ds).ln()).exp()).exp())
                result = self.evaluate(params={"scale": scale, "shape": shape}, time=time)
                self.assertTrue(math.isclose(result.reliability, expected, rel_tol=2e-13, abs_tol=1e-15))
                json.dumps(result.model_dump(mode="json"), allow_nan=False)

    def test_representable_tiny_quantile_against_decimal(self):
        scale, shape, probability = 1e300, 0.002, 0.1
        with localcontext() as ctx:
            ctx.prec = 100
            ds, dk, dp = map(Decimal.from_float, (scale, shape, probability))
            expected = float((ds.ln() + (-(Decimal(1) - dp).ln()).ln() / dk).exp())
        result = self.evaluate(params={"scale": scale, "shape": shape}, time=0.0, probability=probability)
        self.assertGreater(result.quantile_time, 0.0)
        self.assertTrue(math.isclose(result.quantile_time, expected, rel_tol=1e-12))
        json.dumps(result.model_dump(mode="json"), allow_nan=False)

    def test_far_ratio_and_zero_are_json_finite(self):
        for time in (0.0, 1e-300, 1e300):
            with self.subTest(time=time):
                result = self.evaluate(params={"scale": 1e300, "shape": 0.5}, time=time)
                json.dumps(result.model_dump(mode="json"), allow_nan=False)
                self.assertTrue(0 <= result.reliability <= 1)
                self.assertTrue(0 <= result.failure_probability <= 1)

    def test_constructed_unvalidated_request_is_rejected(self):
        request = FixedReliabilityRequest.model_construct(
            model="exponential", parameters={"failure_rate": -1.0}, time=1.0,
            time_unit="hour", quantile_probability=0.1,
        )
        with self.assertRaises(ValidationError):
            evaluate_fixed_reliability(request)

    def test_schema_json_and_repeatability(self):
        first = self.evaluate()
        second = self.evaluate()
        self.assertEqual(first.model_dump(mode="json"), second.model_dump(mode="json"))
        data = json.loads(first.model_dump_json())
        self.assertEqual(FixedReliabilityResult.model_validate(data), first)
        self.assertEqual(data["validation_status"], "synthetic_case_checked")
        self.assertIn("no fitting", data["validation_scope"])


if __name__ == "__main__":
    unittest.main()

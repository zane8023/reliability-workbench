"""Small synthetic numerical checks; not validation for a real mechanism."""
import math
import unittest
from typing import get_args
from pydantic import ValidationError
from app.services.v3_accelerated_solver_service import V3AcceleratedSolverService
from app.validators.v3_accelerated_solver import (
    AccelerationModel, SolverModel, V3AcceleratedLifeEvaluateRequest, V3ParameterSolverRequest,
    V3AcceleratedLifeEvaluateData,
)


class AcceleratedLifeChecks(unittest.TestCase):
    def setUp(self):
        self.solver = V3AcceleratedSolverService()

    def run_arrhenius(self, test, use, unit="K"):
        request = V3AcceleratedLifeEvaluateRequest(
            model_name="arrhenius", temperature_unit=unit,
            parameters={"activation_energy": 0.6, "test_temperature": test, "use_temperature": use},
            life_conversion={"input_life": 100.0, "input_condition": "test", "time_unit": "hour"},
        )
        return self.solver.evaluate_acceleration(request)

    def test_arrhenius_reference_and_life(self):
        result = self.run_arrhenius(343.15, 298.15)
        expected = math.exp(0.6 / 8.617333262145e-5 * (1 / 298.15 - 1 / 343.15))
        self.assertTrue(math.isclose(result["acceleration_factor"], expected, rel_tol=1e-12))
        self.assertTrue(math.isclose(result["converted_life"]["value"], 100 * expected, rel_tol=1e-12))
        self.assertFalse(result["ffr_formal_eligibility"])

    def test_temperature_units_and_repeatability(self):
        kelvin = self.run_arrhenius(343.15, 298.15)["acceleration_factor"]
        celsius = self.run_arrhenius(70.0, 25.0, "degC")["acceleration_factor"]
        self.assertTrue(math.isclose(kelvin, celsius, rel_tol=1e-12))
        self.assertEqual(kelvin, self.run_arrhenius(343.15, 298.15)["acceleration_factor"])

    def test_same_temperature_factor_is_one(self):
        self.assertEqual(self.run_arrhenius(298.15, 298.15)["acceleration_factor"], 1.0)

    def test_missing_parameter_rejected(self):
        request = V3AcceleratedLifeEvaluateRequest(model_name="arrhenius", parameters={"activation_energy": 0.6})
        with self.assertRaises(ValueError):
            self.solver.evaluate_acceleration(request)

    def test_nonfinite_input_rejected(self):
        with self.assertRaises(ValidationError):
            V3AcceleratedLifeEvaluateRequest(model_name="arrhenius", parameters={"activation_energy": float("nan")})

    def test_response_schema_and_json_with_life_conversion(self):
        result = self.run_arrhenius(343.15, 298.15)
        model = V3AcceleratedLifeEvaluateData.model_validate(result)
        self.assertEqual(model.model_dump(mode="json"), result)
        self.assertEqual(V3AcceleratedLifeEvaluateData.model_validate_json(model.model_dump_json()), model)
        self.assertIn("User-supplied", model.provenance["inputs"])
        self.assertIsNotNone(model.converted_life)

    def test_response_schema_and_json_without_life_conversion(self):
        request = V3AcceleratedLifeEvaluateRequest(
            model_name="arrhenius",
            parameters={"activation_energy": 0.6, "test_temperature": 343.15, "use_temperature": 298.15},
        )
        result = self.solver.evaluate_acceleration(request)
        model = V3AcceleratedLifeEvaluateData.model_validate(result)
        self.assertEqual(model.model_dump(mode="json"), result)
        self.assertEqual(V3AcceleratedLifeEvaluateData.model_validate_json(model.model_dump_json()), model)
        self.assertIsNone(model.converted_life)
        self.assertIn("Synthetic", model.provenance["verification"])

    def test_status_reports_only_synthetic_case_scope(self):
        result = self.run_arrhenius(343.15, 298.15)
        self.assertEqual(result["formula_validation_status"], "synthetic_case_checked")
        self.assertIn("synthetic", result["validation_scope"].lower())
        self.assertFalse(result["ffr_formal_eligibility"])

    def test_every_non_arrhenius_model_is_blocked(self):
        for model in get_args(AccelerationModel):
            if model == "arrhenius":
                continue
            with self.subTest(model=model):
                request = V3AcceleratedLifeEvaluateRequest(model_name=model, parameters={})
                with self.assertRaisesRegex(NotImplementedError, "public preview"):
                    self.solver.evaluate_acceleration(request)

    def test_every_parameter_solver_model_is_blocked(self):
        for model in get_args(SolverModel):
            with self.subTest(model=model):
                request = V3ParameterSolverRequest.model_construct(
                    model_name=model, known_parameters={}, target_parameter="x"
                )
                with self.assertRaisesRegex(NotImplementedError, "public preview"):
                    self.solver.solve_parameter(request)

    def test_use_to_test_life_conversion(self):
        forward = self.run_arrhenius(343.15, 298.15)
        request = V3AcceleratedLifeEvaluateRequest(
            model_name="arrhenius",
            parameters={"activation_energy": 0.6, "test_temperature": 343.15, "use_temperature": 298.15},
            life_conversion={"input_life": forward["converted_life"]["value"], "input_condition": "use", "time_unit": "hour"},
        )
        result = self.solver.evaluate_acceleration(request)
        self.assertTrue(math.isclose(result["converted_life"]["value"], 100.0, rel_tol=1e-12))

    def test_unsupported_empirical_model_blocked(self):
        request = V3AcceleratedLifeEvaluateRequest(model_name="lawson", parameters={})
        with self.assertRaises(NotImplementedError):
            self.solver.evaluate_acceleration(request)


if __name__ == "__main__":
    unittest.main()

"""Public calculator inputs must not silently reinterpret booleans as numbers."""
from copy import deepcopy
from decimal import Decimal
import json
from typing import get_args
import unittest
import warnings

from pydantic import ValidationError
from app.validators.fixed_reliability import FixedReliabilityRequest
from app.validators.exponential_fit import ExponentialFitRequest, ExponentialObservation
from app.validators.v3_accelerated_solver import (
    AccelerationModel, V3AcceleratedLifeEvaluateRequest, V3LifeConversionRequest,
)
from app.services.fixed_reliability import evaluate_fixed_reliability
from app.services.exponential_fit import fit_exponential
from app.services.v3_accelerated_solver_service import V3AcceleratedSolverService


FIXED = dict(model="weibull", parameters={"scale": 1000.0, "shape": 2.0},
             time=100.0, time_unit="hour", quantile_probability=0.1)
ARRHENIUS = dict(model_name="arrhenius",
                parameters={"activation_energy": 1.0, "test_temperature": 350.0, "use_temperature": 300.0},
                life_conversion=dict(input_life=100.0, input_condition="test", time_unit="hour"))


class BooleanNumericInputChecks(unittest.TestCase):
    def assert_python_and_json_rejected(self, model, data):
        with self.assertRaises(ValidationError):
            model.model_validate(data)
        with self.assertRaises(ValidationError):
            model.model_validate_json(json.dumps(data))

    def test_fixed_reliability_rejects_boolean_fields(self):
        for value in (True, False):
            for key in ("time", "quantile_probability"):
                data = deepcopy(FIXED); data[key] = value
                with self.subTest(field=key, value=value):
                    self.assert_python_and_json_rejected(FixedReliabilityRequest, data)
            for key in ("scale", "shape"):
                data = deepcopy(FIXED); data["parameters"][key] = value
                with self.subTest(field=key, value=value):
                    self.assert_python_and_json_rejected(FixedReliabilityRequest, data)
            data = dict(model="exponential", parameters={"failure_rate": value}, time=1.0, time_unit="hour")
            with self.subTest(field="failure_rate", value=value):
                self.assert_python_and_json_rejected(FixedReliabilityRequest, data)

    def test_exponential_observations_reject_booleans(self):
        for value in (True, False):
            for kind in ("exact", "right_censored"):
                with self.subTest(kind=kind, value=value):
                    self.assert_python_and_json_rejected(ExponentialObservation, dict(kind=kind, time=value))
                    self.assert_python_and_json_rejected(ExponentialFitRequest,
                        dict(time_unit="hour", observations=[dict(kind=kind, time=value)]))

    def test_arrhenius_rejects_boolean_parameters_and_life(self):
        for value in (True, False):
            for key in ARRHENIUS["parameters"]:
                data = deepcopy(ARRHENIUS); data["parameters"][key] = value
                with self.subTest(field=key, value=value):
                    self.assert_python_and_json_rejected(V3AcceleratedLifeEvaluateRequest, data)
            data = deepcopy(ARRHENIUS); data["life_conversion"]["input_life"] = value
            with self.subTest(field="input_life", value=value):
                self.assert_python_and_json_rejected(V3AcceleratedLifeEvaluateRequest, data)

    def test_ordinary_numeric_coercion_and_results_are_unchanged(self):
        fixed = evaluate_fixed_reliability(FixedReliabilityRequest(**FIXED)).model_dump()
        fit = fit_exponential(ExponentialFitRequest(time_unit="hour",
            observations=[dict(kind="exact", time=2.0), dict(kind="right_censored", time=4.0)])).model_dump()
        solver = V3AcceleratedSolverService()
        accelerated = solver.evaluate_acceleration(V3AcceleratedLifeEvaluateRequest(**ARRHENIUS))
        for convert in (int, float, Decimal, str):
            with self.subTest(convert=convert.__name__):
                data = deepcopy(FIXED)
                data["parameters"] = {key: convert(value) for key, value in data["parameters"].items()}
                data["time"] = convert(data["time"])
                if convert is not int:
                    data["quantile_probability"] = convert(data["quantile_probability"])
                self.assertEqual(evaluate_fixed_reliability(FixedReliabilityRequest(**data)).model_dump(), fixed)
                request = ExponentialFitRequest(time_unit="hour", observations=[
                    dict(kind="exact", time=convert(2)), dict(kind="right_censored", time=convert(4))])
                self.assertEqual(fit_exponential(request).model_dump(), fit)
                data = deepcopy(ARRHENIUS)
                data["parameters"] = {key: convert(value) for key, value in data["parameters"].items()}
                data["life_conversion"]["input_life"] = convert(100)
                self.assertEqual(solver.evaluate_acceleration(V3AcceleratedLifeEvaluateRequest(**data)), accelerated)

    def test_fixed_service_revalidates_constructed_and_mutated_requests(self):
        constructed = FixedReliabilityRequest.model_construct(**deepcopy(FIXED))
        constructed.parameters["shape"] = True
        mutated = FixedReliabilityRequest(**deepcopy(FIXED)); mutated.time = False
        for request in (constructed, mutated):
            with warnings.catch_warnings(), self.assertRaises(ValidationError):
                warnings.simplefilter("ignore", UserWarning)
                evaluate_fixed_reliability(request)

    def test_fit_service_revalidates_constructed_and_mutated_observations(self):
        constructed = ExponentialFitRequest.model_construct(time_unit="hour", observations=[
            ExponentialObservation.model_construct(kind="exact", time=True)])
        mutated = ExponentialFitRequest(time_unit="hour", observations=[dict(kind="exact", time=2)])
        mutated.observations[0].time = True
        for request in (constructed, mutated):
            with warnings.catch_warnings(), self.assertRaises(ValidationError):
                warnings.simplefilter("ignore", UserWarning)
                fit_exponential(request)

    def test_arrhenius_service_revalidates_constructed_and_mutated_requests(self):
        solver = V3AcceleratedSolverService()
        constructed = V3AcceleratedLifeEvaluateRequest.model_construct(
            model_name="arrhenius", parameters={**ARRHENIUS["parameters"], "activation_energy": True})
        life = V3AcceleratedLifeEvaluateRequest.model_construct(model_name="arrhenius",
            parameters=deepcopy(ARRHENIUS["parameters"]), life_conversion=V3LifeConversionRequest.model_construct(
                input_life=True, input_condition="test", time_unit="hour"))
        mutated = V3AcceleratedLifeEvaluateRequest(**deepcopy(ARRHENIUS)); mutated.parameters["test_temperature"] = True
        for request in (constructed, life, mutated):
            with warnings.catch_warnings(), self.assertRaises(ValidationError):
                warnings.simplefilter("ignore", UserWarning)
                solver.evaluate_acceleration(request)

    def test_unsupported_acceleration_models_remain_blocked_first(self):
        solver = V3AcceleratedSolverService()
        for model in get_args(AccelerationModel):
            if model != "arrhenius":
                with self.subTest(model=model), self.assertRaises(NotImplementedError):
                    solver.evaluate_acceleration(V3AcceleratedLifeEvaluateRequest.model_construct(
                        model_name=model, parameters={"invalid": True}))

    def test_public_numeric_json_schema_is_preserved(self):
        for model, field in ((FixedReliabilityRequest, "time"),
                             (ExponentialObservation, "time"), (V3LifeConversionRequest, "input_life")):
            self.assertEqual(model.model_json_schema()["properties"][field]["type"], "number")
        for model in (FixedReliabilityRequest, V3AcceleratedLifeEvaluateRequest):
            self.assertEqual(model.model_json_schema()["properties"]["parameters"]["additionalProperties"]["type"], "number")

    def test_valid_numeric_zero_boundaries_are_preserved(self):
        data = deepcopy(FIXED); data["time"] = 0
        result = evaluate_fixed_reliability(FixedReliabilityRequest(**data))
        self.assertEqual((result.reliability, result.failure_probability, result.hazard_rate), (1.0, 0.0, 0.0))
        data = deepcopy(ARRHENIUS); data["parameters"]["activation_energy"] = 0
        self.assertEqual(V3AcceleratedSolverService().evaluate_acceleration(
            V3AcceleratedLifeEvaluateRequest(**data))["acceleration_factor"], 1.0)
        data = deepcopy(ARRHENIUS); data["temperature_unit"] = "degC"
        data["parameters"].update(test_temperature=25, use_temperature=0)
        self.assertGreater(V3AcceleratedSolverService().evaluate_acceleration(
            V3AcceleratedLifeEvaluateRequest(**data))["acceleration_factor"], 1.0)


if __name__ == "__main__":
    unittest.main()

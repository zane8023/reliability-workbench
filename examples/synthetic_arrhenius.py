"""Illustrative synthetic numbers only; not a calibrated engineering prediction."""
import math
from pydantic import ValidationError
from app.services.v3_accelerated_solver_service import V3AcceleratedSolverService
from app.validators.v3_accelerated_solver import V3AcceleratedLifeEvaluateRequest

solver = V3AcceleratedSolverService()
request = V3AcceleratedLifeEvaluateRequest(
    model_name="arrhenius",
    parameters={"activation_energy": 0.6, "test_temperature": 343.15, "use_temperature": 298.15},
    temperature_unit="K", activation_energy_unit="eV",
    life_conversion={"input_life": 100.0, "input_condition": "test", "time_unit": "hour"},
)
reference = math.exp(0.6 / 8.617333262145e-5 * (1 / 298.15 - 1 / 343.15))
first = solver.evaluate_acceleration(request)
second = solver.evaluate_acceleration(request)
assert math.isclose(first["acceleration_factor"], reference, rel_tol=1e-12)
assert math.isclose(first["converted_life"]["value"], 100 * reference, rel_tol=1e-12)
assert first["acceleration_factor"] == second["acceleration_factor"]
assert first["ffr_formal_eligibility"] is False
try:
    V3AcceleratedLifeEvaluateRequest(model_name="arrhenius", parameters={"activation_energy": float("nan")})
except ValidationError:
    pass
else:
    raise AssertionError("non-finite input must be rejected")
print(f"Synthetic Arrhenius factor: {reference:.6f}")
print("Arithmetic, repeatability and non-finite input checks passed.")

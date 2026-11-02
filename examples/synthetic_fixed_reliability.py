"""Synthetic Weibull example; not a field prediction."""
from app.validators.fixed_reliability import FixedReliabilityRequest
from app.services.fixed_reliability import evaluate_fixed_reliability

request = FixedReliabilityRequest(model="weibull", parameters={"scale": 1000.0, "shape": 2.0},
                                  time=100.0, time_unit="hour", quantile_probability=0.1)
result = evaluate_fixed_reliability(request)
print(result.model_dump_json(indent=2))

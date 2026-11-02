"""Synthetic exponential point fit; not a field prediction."""
from app.validators.exponential_fit import ExponentialFitRequest
from app.services.exponential_fit import fit_exponential

request = ExponentialFitRequest(time_unit="hour", observations=[
    {"kind": "exact", "time": 1}, {"kind": "exact", "time": 2},
    {"kind": "exact", "time": 3}, {"kind": "right_censored", "time": 4},
    {"kind": "right_censored", "time": 5},
])
print(fit_exponential(request).model_dump_json(indent=2))

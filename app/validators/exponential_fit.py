"""Input and output contracts for a narrow exponential point estimate."""
import math
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExponentialObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["exact", "right_censored"]
    time: float = Field(gt=0)

    @model_validator(mode="after")
    def finite_time(self):
        if not math.isfinite(self.time):
            raise ValueError("observation time must be finite")
        return self


class ExponentialFitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observations: List[ExponentialObservation] = Field(min_length=1, max_length=10000)
    time_unit: Literal["second", "minute", "hour", "day", "year"]


class ExponentialFitResult(BaseModel):
    model: Literal["exponential"]
    method: Literal["maximum_likelihood_point_estimate"]
    sample_count: int
    failure_count: int
    right_censored_count: int
    total_exposure: Optional[float]
    exposure_scale: float
    exposure_scaled_sum: float
    time_unit: str
    failure_rate: float
    failure_rate_unit: str
    scale: float
    validation_status: Literal["synthetic_case_checked"]
    validation_scope: str
    assumptions: List[str]
    warnings: List[str]
    provenance: Dict[str, str]

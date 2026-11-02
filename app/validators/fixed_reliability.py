"""Contracts for fixed-parameter lifetime distribution calculations."""
import math
from typing import Dict, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class FixedReliabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: Literal["weibull", "exponential"]
    parameters: Dict[str, float]
    time: float = Field(ge=0)
    time_unit: Literal["second", "minute", "hour", "day", "year"]
    quantile_probability: float = Field(default=0.1, gt=0, lt=1)

    @model_validator(mode="after")
    def validate_inputs(self):
        expected = {"scale", "shape"} if self.model == "weibull" else {"failure_rate"}
        if set(self.parameters) != expected:
            raise ValueError("parameters must match the selected model exactly")
        if not math.isfinite(self.time) or not math.isfinite(self.quantile_probability):
            raise ValueError("time and probability must be finite")
        if any(not math.isfinite(v) or v <= 0 for v in self.parameters.values()):
            raise ValueError("distribution parameters must be finite and positive")
        return self


class FixedReliabilityResult(BaseModel):
    model: Literal["weibull", "exponential"]
    parameters: Dict[str, float]
    time: float
    time_unit: str
    reliability: float
    failure_probability: float
    hazard_rate: Optional[float]
    hazard_unit: str
    quantile_probability: float
    quantile_time: float
    validation_status: Literal["synthetic_case_checked"]
    validation_scope: str
    provenance: Dict[str, str]
    warnings: list[str]

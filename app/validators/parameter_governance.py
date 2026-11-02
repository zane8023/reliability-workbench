from __future__ import annotations

import math
from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ExplicitFFRMapping(BaseModel):
    model: Literal["constant_hazard_inverse_life"]
    baseline_ffr: float = Field(..., ge=0)
    baseline_life_hours: float = Field(..., gt=0)
    metric_type: Literal["hazard_rate", "ppm", "fit"]
    unit: str = Field(..., min_length=1, max_length=80)
    exposure_basis: str = Field(..., min_length=1, max_length=200)

    @model_validator(mode="after")
    def finite_values(self):
        if not math.isfinite(self.baseline_ffr) or not math.isfinite(
            self.baseline_life_hours
        ):
            raise ValueError("FFR mapping values must be finite")
        return self

class ParameterGovernanceContext(BaseModel):
    parameter_id: Optional[str] = Field(None, min_length=1, max_length=160)
    mechanism_id: Optional[str] = Field(None, min_length=1, max_length=100)
    authorize_restricted_scenario: bool = False
    custom_ea_scenarios_eV: Dict[str, float] = Field(
        default_factory=dict, max_length=20
    )
    test_life_hours: Optional[float] = Field(None, gt=0)
    ffr_mapping: Optional[ExplicitFFRMapping] = None

    @model_validator(mode="after")
    def validate_scenarios(self):
        if any(
            not name.strip()
            or not math.isfinite(value)
            or value <= 0
            or value > 10
            for name, value in self.custom_ea_scenarios_eV.items()
        ):
            raise ValueError(
                "custom Ea scenario names must be non-empty and values must "
                "be finite within (0, 10] eV"
            )
        if self.test_life_hours is not None and not math.isfinite(
            self.test_life_hours
        ):
            raise ValueError("test_life_hours must be finite")
        if self.ffr_mapping is not None and self.test_life_hours is None:
            raise ValueError("FFR mapping requires test_life_hours")
        return self

from __future__ import annotations

import math
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.validators.parameter_governance import ParameterGovernanceContext
from app.validators.numeric_inputs import NonBooleanFloat


AccelerationModel = Literal[
    "arrhenius",
    "temperature_eyring",
    "inverse_power",
    "coffin_manson",
    "norris_landzberg",
    "peck",
    "hallberg_peck",
    "black_equation",
    "modified_coffin_manson",
    "lawson",
]

SolverModel = Literal[
    "arrhenius",
    "temperature_eyring",
    "inverse_power",
    "coffin_manson",
    "norris_landzberg",
    "peck",
    "hallberg_peck",
    "black_equation",
    "weibull",
    "exponential_reliability",
    "zero_failure_demonstration",
    "constant_hazard_ffr",
    "multi_stage_equivalent_exposure",
    "modified_coffin_manson",
    "lawson",
]

TimeUnit = Literal["second", "minute", "hour", "day", "year"]


class V3LifeConversionRequest(BaseModel):
    input_life: NonBooleanFloat = Field(..., gt=0)
    input_condition: Literal["test", "use"]
    time_unit: TimeUnit

    @model_validator(mode="after")
    def finite_life(self):
        if not math.isfinite(self.input_life):
            raise ValueError("input_life must be finite")
        return self


class V3AcceleratedLifeEvaluateRequest(BaseModel):
    model_name: AccelerationModel
    parameters: Dict[str, NonBooleanFloat]
    temperature_unit: Literal["K", "degC"] = "K"
    activation_energy_unit: Literal["eV", "J/mol"] = "eV"
    humidity_unit: Literal["fraction", "percent"] = "fraction"
    life_conversion: Optional[V3LifeConversionRequest] = None
    governance_context: Optional[ParameterGovernanceContext] = None

    @model_validator(mode="after")
    def finite_parameters(self):
        if any(not math.isfinite(value) for value in self.parameters.values()):
            raise ValueError("all parameters must be finite")
        return self


class V3AccelerationLifeResult(BaseModel):
    value: float
    condition: Literal["test", "use"]
    unit: str


class V3AcceleratedLifeEvaluateData(BaseModel):
    model_name: str
    formula_id: str
    formula_version: str
    acceleration_factor: float
    log_acceleration_factor: float
    canonical_parameters: Dict[str, float]
    canonical_units: Dict[str, str]
    converted_life: Optional[V3AccelerationLifeResult]
    calculation_steps: List[Dict[str, object]]
    assumptions: List[str]
    warnings: List[str]
    formula_validation_status: str
    validation_scope: str
    ffr_formal_eligibility: bool
    blocking_reasons: List[str]
    provenance: Dict[str, Any]


class V3AcceleratedLifeEvaluateResponse(BaseModel):
    status_code: int
    message: str
    data: V3AcceleratedLifeEvaluateData
    warning: List[str] = Field(default_factory=list)
    error: None = None


class V3EquivalentExposureStage(BaseModel):
    duration: float = Field(..., gt=0)
    acceleration_factor: float = Field(..., gt=0)

    @model_validator(mode="after")
    def finite_stage(self):
        if not math.isfinite(self.duration) or not math.isfinite(
            self.acceleration_factor
        ):
            raise ValueError("stage values must be finite")
        return self


class V3ParameterSolverRequest(BaseModel):
    model_name: SolverModel
    known_parameters: Dict[str, float]
    target_parameter: str = Field(..., min_length=1, max_length=80)
    units: Dict[str, str] = Field(default_factory=dict)
    constraints: Dict[str, float] = Field(default_factory=dict)
    initial_guess: Optional[float] = None
    solver_method: Literal["auto", "analytic", "brentq"] = "auto"
    tolerance: float = Field(1e-8, gt=0, le=1e-3)
    stages: Optional[List[V3EquivalentExposureStage]] = None
    governance_context: Optional[ParameterGovernanceContext] = None

    @model_validator(mode="after")
    def validate_numbers(self):
        values = list(self.known_parameters.values()) + list(
            self.constraints.values()
        )
        if self.initial_guess is not None:
            values.append(self.initial_guess)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("known parameters, constraints and guess must be finite")
        if set(self.constraints) - {"min", "max"}:
            raise ValueError("constraints only support min and max")
        if (
            "min" in self.constraints
            and "max" in self.constraints
            and self.constraints["min"] > self.constraints["max"]
        ):
            raise ValueError("constraint min cannot exceed max")
        if self.model_name == "multi_stage_equivalent_exposure":
            if not self.stages:
                raise ValueError("non-empty stages are required")
        elif self.stages is not None:
            raise ValueError("stages are only valid for multi-stage exposure")
        return self


class V3BackSubstitutionResult(BaseModel):
    verification_type: str
    predicted_value: float
    reference_value: float
    absolute_error: float
    relative_error: float
    passed: bool


class V3ParameterSolverData(BaseModel):
    model_name: str
    target_parameter: str
    solved_value: float
    solved_unit: str
    all_candidates: List[float]
    solution_count: int
    solver_status: str
    solver_method: str
    formula_id: str
    formula_version: str
    canonical_known_parameters: Dict[str, float]
    back_substitution: V3BackSubstitutionResult
    calculation_steps: List[Dict[str, object]]
    assumptions: List[str]
    warnings: List[str]
    formula_validation_status: str
    ffr_formal_eligibility: bool
    blocking_reasons: List[str]
    provenance: Dict[str, Any]


class V3ParameterSolverResponse(BaseModel):
    status_code: int
    message: str
    data: V3ParameterSolverData
    warning: List[str] = Field(default_factory=list)
    error: None = None

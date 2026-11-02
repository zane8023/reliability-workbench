from __future__ import annotations

import math
from typing import Dict, Iterable, List, Tuple

from scipy.optimize import brentq

from app.validators.v3_accelerated_solver import (
    V3AcceleratedLifeEvaluateRequest,
    V3ParameterSolverRequest,
)


K_B_EV_PER_K = 8.617333262145e-5
J_PER_MOL_PER_EV = 96485.33212
MAX_LOG_FLOAT = 700.0
BLOCKED_MODELS = {"modified_coffin_manson", "lawson"}


EVALUATION_KEYS = {
    "arrhenius": {
        "activation_energy",
        "test_temperature",
        "use_temperature",
    },
    "temperature_eyring": {
        "activation_energy",
        "test_temperature",
        "use_temperature",
    },
    "inverse_power": {"test_stress", "use_stress", "stress_exponent"},
    "coffin_manson": {
        "test_delta_temperature",
        "use_delta_temperature",
        "fatigue_exponent",
    },
    "norris_landzberg": {
        "activation_energy",
        "test_delta_temperature",
        "use_delta_temperature",
        "test_frequency",
        "use_frequency",
        "fatigue_exponent",
        "frequency_exponent",
        "test_max_temperature",
        "use_max_temperature",
    },
    "peck": {
        "activation_energy",
        "test_temperature",
        "use_temperature",
        "test_humidity",
        "use_humidity",
        "humidity_exponent",
    },
    "hallberg_peck": {
        "activation_energy",
        "test_temperature",
        "use_temperature",
        "test_humidity",
        "use_humidity",
        "humidity_exponent",
    },
    "black_equation": {
        "activation_energy",
        "test_temperature",
        "use_temperature",
        "test_current_density",
        "use_current_density",
        "current_exponent",
    },
}


FORMULA_IDS = {
    "arrhenius": "v3.accelerated_life.arrhenius.v1",
    "temperature_eyring": "v3.accelerated_life.temperature_eyring.v1",
    "inverse_power": "v3.accelerated_life.inverse_power.v1",
    "coffin_manson": "v3.accelerated_life.coffin_manson.v1",
    "norris_landzberg": "v3.accelerated_life.norris_landzberg.v1",
    "peck": "v3.accelerated_life.peck.v1",
    "hallberg_peck": "v3.accelerated_life.hallberg_peck.v1",
    "black_equation": "v3.accelerated_life.black_equation.v1",
    "weibull": "v3.parameter_solver.weibull.v1",
    "exponential_reliability": "v3.parameter_solver.exponential.v1",
    "zero_failure_demonstration": "v3.parameter_solver.zero_failure.v1",
    "constant_hazard_ffr": "v3.parameter_solver.constant_hazard.v1",
    "multi_stage_equivalent_exposure": (
        "v3.parameter_solver.equivalent_exposure.v1"
    ),
}


class V3AcceleratedSolverService:
    def evaluate_acceleration(
        self, request: V3AcceleratedLifeEvaluateRequest
    ) -> Dict[str, object]:
        if request.model_name != "arrhenius":
            raise NotImplementedError(
                "Only forward Arrhenius evaluation is included in this public preview."
            )
        parameters = self._canonicalize_evaluation(request)
        log_af, steps = self._log_acceleration_factor(
            request.model_name, parameters
        )
        acceleration_factor = self._safe_exp(log_af)

        converted_life = None
        if request.life_conversion:
            if request.life_conversion.input_condition == "test":
                value = request.life_conversion.input_life * acceleration_factor
                condition = "use"
                expression = "life_use = life_test * AF"
            else:
                value = request.life_conversion.input_life / acceleration_factor
                condition = "test"
                expression = "life_test = life_use / AF"
            self._require_finite_positive(value, "converted life")
            converted_life = {
                "value": value,
                "condition": condition,
                "unit": request.life_conversion.time_unit,
            }
            steps.append(
                {
                    "step": "life_conversion",
                    "expression": expression,
                    "result": value,
                }
            )

        warnings = [
            "Synthetic example checks do not validate product-specific parameters.",
            "Mechanism, parameter evidence, input-domain and hash gates remain required.",
        ]
        if acceleration_factor < 1:
            warnings.append(
                "AF is below one; the declared test condition is less accelerating "
                "than the use condition under this model."
            )
        return {
            "model_name": request.model_name,
            "formula_id": FORMULA_IDS[request.model_name],
            "formula_version": "1.0.0",
            "acceleration_factor": acceleration_factor,
            "log_acceleration_factor": log_af,
            "canonical_parameters": parameters,
            "canonical_units": self._canonical_units(parameters),
            "converted_life": converted_life,
            "calculation_steps": steps,
            "assumptions": self._assumptions(request.model_name),
            "warnings": warnings,
            "formula_validation_status": "synthetic_case_checked",
            "validation_scope": "Forward Arrhenius synthetic examples only; mechanism, parameters and field predictions are not validated.",
            "provenance": {
                "formula": {
                    "id": FORMULA_IDS["arrhenius"],
                    "reference_for_comparison": "https://www.itl.nist.gov/div898/handbook/apr/section1/apr151.htm",
                    "reference_note": "Reference for the Arrhenius acceleration-factor form; original code authorship not established by this reference.",
                },
                "boltzmann_constant": {
                    "value": K_B_EV_PER_K,
                    "unit": "eV/K",
                    "reference_for_comparison": "https://physics.nist.gov/cuu/Constants/index.html",
                    "note": "Rounded value used by this implementation; compare with CODATA SI constants.",
                },
                "inputs": "User-supplied; no parameter calibration or mechanism evidence is assumed.",
                "verification": "Synthetic examples and focused software checks only; not field or product validation.",
            },
            "ffr_formal_eligibility": False,
            "blocking_reasons": [
                "formal eligibility requires validated mechanism and parameters"
            ],
        }

    def solve_parameter(
        self, request: V3ParameterSolverRequest
    ) -> Dict[str, object]:
        raise NotImplementedError(
            "Parameter solving is not included in this public preview."
        )

    def _canonicalize_evaluation(
        self, request: V3AcceleratedLifeEvaluateRequest
    ) -> Dict[str, float]:
        expected = EVALUATION_KEYS[request.model_name]
        supplied = set(request.parameters)
        if supplied != expected:
            raise ValueError(
                f"{request.model_name} parameters must be exactly "
                f"{sorted(expected)}"
            )
        values = dict(request.parameters)
        self._convert_common_units(
            values,
            request.temperature_unit,
            request.activation_energy_unit,
            request.humidity_unit,
        )
        self._validate_physical_parameters(values)
        return values

    def _canonicalize_solver_known(
        self, request: V3ParameterSolverRequest
    ) -> Dict[str, float]:
        known = dict(request.known_parameters)
        temperature_unit = request.units.get("temperature", "K")
        ea_unit = request.units.get("activation_energy", "eV")
        humidity_unit = request.units.get("humidity", "fraction")
        if temperature_unit not in {"K", "degC"}:
            raise ValueError("temperature unit must be K or degC")
        if ea_unit not in {"eV", "J/mol"}:
            raise ValueError("activation energy unit must be eV or J/mol")
        if humidity_unit not in {"fraction", "percent"}:
            raise ValueError("humidity unit must be fraction or percent")
        self._convert_common_units(
            known, temperature_unit, ea_unit, humidity_unit
        )
        return known

    @staticmethod
    def _convert_common_units(
        values: Dict[str, float],
        temperature_unit: str,
        activation_energy_unit: str,
        humidity_unit: str,
    ) -> None:
        if "activation_energy" in values and activation_energy_unit == "J/mol":
            values["activation_energy"] /= J_PER_MOL_PER_EV
        if temperature_unit == "degC":
            for key in list(values):
                if "temperature" in key and "delta_temperature" not in key:
                    values[key] += 273.15
        if humidity_unit == "percent":
            for key in list(values):
                if "humidity" in key and "exponent" not in key:
                    values[key] /= 100.0

    def _validate_physical_parameters(self, values: Dict[str, float]) -> None:
        for key, value in values.items():
            self._require_finite(value, key)
            if key == "activation_energy":
                if value < 0:
                    raise ValueError("activation_energy must be non-negative")
            elif "humidity" in key and "exponent" not in key:
                if not 0 < value <= 1:
                    raise ValueError(f"{key} must be in (0, 1]")
            elif "temperature" in key and "delta_temperature" not in key:
                if value <= 0:
                    raise ValueError(f"{key} must be greater than absolute zero")
            elif key.endswith("_exponent"):
                if value < 0:
                    raise ValueError(f"{key} must be non-negative")
            elif value <= 0:
                raise ValueError(f"{key} must be greater than zero")

    def _log_acceleration_factor(
        self, model: str, p: Dict[str, float]
    ) -> Tuple[float, List[Dict[str, object]]]:
        thermal = 0.0
        if model in {
            "arrhenius",
            "temperature_eyring",
            "peck",
            "hallberg_peck",
            "black_equation",
        }:
            thermal = p["activation_energy"] / K_B_EV_PER_K * (
                1.0 / p["use_temperature"]
                - 1.0 / p["test_temperature"]
            )

        if model == "arrhenius":
            log_af = thermal
        elif model == "temperature_eyring":
            log_af = (
                math.log(p["test_temperature"] / p["use_temperature"])
                + thermal
            )
        elif model == "inverse_power":
            log_af = p["stress_exponent"] * math.log(
                p["test_stress"] / p["use_stress"]
            )
        elif model == "coffin_manson":
            log_af = p["fatigue_exponent"] * math.log(
                p["test_delta_temperature"] / p["use_delta_temperature"]
            )
        elif model == "norris_landzberg":
            log_af = (
                p["fatigue_exponent"]
                * math.log(
                    p["test_delta_temperature"]
                    / p["use_delta_temperature"]
                )
                + p["frequency_exponent"]
                * math.log(p["use_frequency"] / p["test_frequency"])
                + p["activation_energy"]
                / K_B_EV_PER_K
                * (
                    1.0 / p["use_max_temperature"]
                    - 1.0 / p["test_max_temperature"]
                )
            )
        elif model in {"peck", "hallberg_peck"}:
            log_af = (
                p["humidity_exponent"]
                * math.log(p["test_humidity"] / p["use_humidity"])
                + thermal
            )
        elif model == "black_equation":
            log_af = (
                p["current_exponent"]
                * math.log(
                    p["test_current_density"] / p["use_current_density"]
                )
                + thermal
            )
        else:
            raise ValueError(f"unsupported acceleration model: {model}")
        self._require_finite(log_af, "log acceleration factor")
        return log_af, [
            {
                "step": "evaluate_log_af",
                "model": model,
                "result": log_af,
            },
            {
                "step": "exponentiate",
                "expression": "AF = exp(log_AF)",
            },
        ]

    def _dispatch_solver(
        self, request: V3ParameterSolverRequest, known: Dict[str, float]
    ) -> Tuple[float, str, str, Dict[str, object]]:
        model = request.model_name
        target = request.target_parameter
        if model in EVALUATION_KEYS:
            value, unit, method = self._solve_acceleration_parameter(
                model, known, target, request
            )
        elif model == "weibull":
            value, unit, method = self._solve_weibull(known, target, request)
        elif model == "exponential_reliability":
            value, unit, method = self._solve_exponential(
                known, target, request
            )
        elif model == "zero_failure_demonstration":
            value, unit, method = self._solve_zero_failure(
                known, target, request
            )
        elif model == "constant_hazard_ffr":
            value, unit, method = self._solve_constant_hazard(
                known, target, request
            )
        elif model == "multi_stage_equivalent_exposure":
            self._require_exact(known, set(), model, target)
            if target != "equivalent_use_exposure":
                raise ValueError(
                    "multi-stage exposure only solves equivalent_use_exposure"
                )
            value = sum(
                stage.duration * stage.acceleration_factor
                for stage in request.stages or []
            )
            unit = request.units.get("time", "hour")
            method = "analytic_sum"
        else:
            raise ValueError(f"unsupported solver model: {model}")

        verification = self._verify_solution(request, known, value)
        return value, unit, method, verification

    def _verify_solution(
        self,
        request: V3ParameterSolverRequest,
        known: Dict[str, float],
        value: float,
    ) -> Dict[str, object]:
        model = request.model_name
        target = request.target_parameter

        if model in EVALUATION_KEYS:
            if target == "acceleration_factor":
                parameters = dict(known)
                reference = value
            else:
                parameters = {
                    key: parameter
                    for key, parameter in known.items()
                    if key != "acceleration_factor"
                }
                parameters[target] = value
                reference = known["acceleration_factor"]
            log_af, _ = self._log_acceleration_factor(model, parameters)
            return self._verification_record(
                self._safe_exp(log_af),
                reference,
                "acceleration_factor_back_substitution",
            )

        if model == "weibull":
            if target in {"scale", "shape"}:
                scale = value if target == "scale" else known["scale"]
                shape = value if target == "shape" else known["shape"]
                if "quantile_life" in known:
                    predicted = scale * (
                        -math.log(1.0 - known["quantile_probability"])
                    ) ** (1.0 / shape)
                    reference = known["quantile_life"]
                    kind = "weibull_quantile_back_substitution"
                else:
                    predicted = math.exp(
                        -((known["time"] / scale) ** shape)
                    )
                    reference = known["reliability"]
                    kind = "weibull_reliability_back_substitution"
            elif target == "quantile_life":
                predicted = 1.0 - math.exp(
                    -((value / known["scale"]) ** known["shape"])
                )
                reference = known["quantile_probability"]
                kind = "weibull_quantile_probability_back_substitution"
            elif target == "reliability":
                predicted = math.exp(
                    -((known["time"] / known["scale"]) ** known["shape"])
                )
                reference = value
                kind = "weibull_reliability_back_substitution"
            else:
                predicted = math.exp(
                    -((value / known["scale"]) ** known["shape"])
                )
                reference = known["reliability"]
                kind = "weibull_time_back_substitution"
            return self._verification_record(predicted, reference, kind)

        if model == "exponential_reliability":
            if target == "reliability":
                predicted = math.exp(
                    -known["hazard_rate"] * known["time"]
                )
                reference = value
            elif target == "hazard_rate":
                predicted = math.exp(-value * known["time"])
                reference = known["reliability"]
            else:
                predicted = math.exp(-known["hazard_rate"] * value)
                reference = known["reliability"]
            return self._verification_record(
                predicted, reference, "exponential_reliability_back_substitution"
            )

        if model == "zero_failure_demonstration":
            if target == "sample_size":
                achieved = (1.0 - known["confidence"]) ** (1.0 / value)
                target_reliability = known["target_reliability"]
                shortfall = max(0.0, target_reliability - achieved)
                return {
                    "verification_type": "zero_failure_reliability_inequality",
                    "predicted_value": achieved,
                    "reference_value": target_reliability,
                    "absolute_error": shortfall,
                    "relative_error": shortfall / target_reliability,
                    "passed": achieved >= target_reliability,
                }
            if target in {
                "failure_probability_upper",
                "demonstrated_reliability",
            }:
                reliability = (1.0 - known["confidence"]) ** (
                    1.0 / known["sample_size"]
                )
                predicted = (
                    1.0 - reliability
                    if target == "failure_probability_upper"
                    else reliability
                )
                return self._verification_record(
                    predicted, value, "zero_failure_exact_binomial_back_substitution"
                )
            if target == "test_time":
                predicted = -math.log(1.0 - known["confidence"]) / (
                    known["sample_size"] * value
                )
                reference = known["target_rate"]
            else:
                predicted = -math.log(1.0 - known["confidence"]) / (
                    known["sample_size"] * known["test_time"]
                )
                reference = value
            return self._verification_record(
                predicted, reference, "zero_event_poisson_back_substitution"
            )

        if model == "constant_hazard_ffr":
            failures = value if target == "failures" else known["failures"]
            sample_size = (
                value if target == "sample_size" else known["sample_size"]
            )
            test_time = value if target == "test_time" else known["test_time"]
            predicted_rate = failures / (sample_size * test_time)
            reference_rate = (
                value if target == "hazard_rate" else known["hazard_rate"]
            )
            return self._verification_record(
                predicted_rate,
                reference_rate,
                "constant_hazard_rate_back_substitution",
            )

        predicted = sum(
            stage.duration * stage.acceleration_factor
            for stage in request.stages or []
        )
        return self._verification_record(
            predicted, value, "equivalent_exposure_back_substitution"
        )

    @staticmethod
    def _verification_record(
        predicted: float, reference: float, verification_type: str
    ) -> Dict[str, object]:
        absolute_error = abs(predicted - reference)
        relative_error = absolute_error / max(abs(reference), 1e-15)
        return {
            "verification_type": verification_type,
            "predicted_value": predicted,
            "reference_value": reference,
            "absolute_error": absolute_error,
            "relative_error": relative_error,
            "passed": math.isfinite(relative_error),
        }

    def _solve_acceleration_parameter(
        self,
        model: str,
        known: Dict[str, float],
        target: str,
        request: V3ParameterSolverRequest,
    ) -> Tuple[float, str, str]:
        if target == "acceleration_factor":
            self._require_exact(
                known, EVALUATION_KEYS[model], model, target
            )
            self._validate_physical_parameters(known)
            log_af, _ = self._log_acceleration_factor(model, known)
            return self._safe_exp(log_af), "dimensionless", "analytic"

        if model == "arrhenius":
            return self._solve_arrhenius(known, target)
        if model == "temperature_eyring":
            return self._solve_temperature_eyring(known, target, request)
        if model == "inverse_power":
            return self._solve_power_ratio(
                known,
                target,
                "test_stress",
                "use_stress",
                "stress_exponent",
            )
        if model == "coffin_manson":
            return self._solve_power_ratio(
                known,
                target,
                "test_delta_temperature",
                "use_delta_temperature",
                "fatigue_exponent",
            )
        if model in {"peck", "hallberg_peck"}:
            return self._solve_peck_or_black(
                known,
                target,
                ratio_test="test_humidity",
                ratio_use="use_humidity",
                exponent="humidity_exponent",
            )
        if model == "black_equation":
            return self._solve_peck_or_black(
                known,
                target,
                ratio_test="test_current_density",
                ratio_use="use_current_density",
                exponent="current_exponent",
            )
        raise ValueError(
            f"{model} only supports acceleration_factor in the unified solver"
        )

    def _solve_arrhenius(
        self, known: Dict[str, float], target: str
    ) -> Tuple[float, str, str]:
        if target == "activation_energy":
            self._require_exact(
                known,
                {
                    "acceleration_factor",
                    "test_temperature",
                    "use_temperature",
                },
                "arrhenius",
                target,
            )
            self._positive_keys(
                known,
                "acceleration_factor",
                "test_temperature",
                "use_temperature",
            )
            denominator = (
                1.0 / known["use_temperature"]
                - 1.0 / known["test_temperature"]
            )
            if denominator == 0:
                raise ValueError("equal temperatures cannot identify Ea")
            value = K_B_EV_PER_K * math.log(
                known["acceleration_factor"]
            ) / denominator
            if value < 0:
                raise ValueError("solution implies a negative activation energy")
            return value, "eV", "analytic"
        if target in {"test_temperature", "use_temperature"}:
            other = (
                "use_temperature"
                if target == "test_temperature"
                else "test_temperature"
            )
            self._require_exact(
                known,
                {"activation_energy", "acceleration_factor", other},
                "arrhenius",
                target,
            )
            self._positive_keys(
                known, "activation_energy", "acceleration_factor", other
            )
            ratio = (
                K_B_EV_PER_K
                * math.log(known["acceleration_factor"])
                / known["activation_energy"]
            )
            reciprocal = (
                1.0 / known[other] - ratio
                if target == "test_temperature"
                else 1.0 / known[other] + ratio
            )
            if reciprocal <= 0:
                raise ValueError("no positive absolute-temperature solution")
            return 1.0 / reciprocal, "K", "analytic"
        raise ValueError(f"unsupported arrhenius target: {target}")

    def _solve_temperature_eyring(
        self,
        known: Dict[str, float],
        target: str,
        request: V3ParameterSolverRequest,
    ) -> Tuple[float, str, str]:
        if target == "activation_energy":
            required = {
                "acceleration_factor",
                "test_temperature",
                "use_temperature",
            }
            self._require_exact(known, required, "temperature_eyring", target)
            self._positive_keys(known, *required)
            denominator = (
                1.0 / known["use_temperature"]
                - 1.0 / known["test_temperature"]
            )
            if denominator == 0:
                raise ValueError("equal temperatures cannot identify Ea")
            numerator = math.log(known["acceleration_factor"]) - math.log(
                known["test_temperature"] / known["use_temperature"]
            )
            value = K_B_EV_PER_K * numerator / denominator
            if value < 0:
                raise ValueError("solution implies a negative activation energy")
            return value, "eV", "analytic"
        if target in {"test_temperature", "use_temperature"}:
            other = (
                "use_temperature"
                if target == "test_temperature"
                else "test_temperature"
            )
            self._require_exact(
                known,
                {"activation_energy", "acceleration_factor", other},
                "temperature_eyring",
                target,
            )
            self._positive_keys(
                known, "activation_energy", "acceleration_factor", other
            )

            def residual(candidate: float) -> float:
                p = {
                    "activation_energy": known["activation_energy"],
                    target: candidate,
                    other: known[other],
                }
                log_af, _ = self._log_acceleration_factor(
                    "temperature_eyring", p
                )
                return log_af - math.log(known["acceleration_factor"])

            value = self._bounded_root(residual, request)
            return value, "K", "brentq"
        raise ValueError(f"unsupported temperature_eyring target: {target}")

    def _solve_power_ratio(
        self,
        known: Dict[str, float],
        target: str,
        test_key: str,
        use_key: str,
        exponent_key: str,
    ) -> Tuple[float, str, str]:
        model = "inverse_power" if test_key == "test_stress" else "coffin_manson"
        if target == exponent_key:
            self._require_exact(
                known,
                {"acceleration_factor", test_key, use_key},
                model,
                target,
            )
            self._positive_keys(
                known, "acceleration_factor", test_key, use_key
            )
            denominator = math.log(known[test_key] / known[use_key])
            if denominator == 0:
                raise ValueError("equal stress levels cannot identify exponent")
            value = math.log(known["acceleration_factor"]) / denominator
            if value < 0:
                raise ValueError("solution implies a negative exponent")
            return value, "dimensionless", "analytic"
        if target in {test_key, use_key}:
            other = use_key if target == test_key else test_key
            self._require_exact(
                known,
                {"acceleration_factor", exponent_key, other},
                model,
                target,
            )
            self._positive_keys(
                known, "acceleration_factor", exponent_key, other
            )
            if known[exponent_key] == 0:
                raise ValueError("zero exponent cannot identify stress")
            root = known["acceleration_factor"] ** (
                1.0 / known[exponent_key]
            )
            value = known[other] * root if target == test_key else known[other] / root
            return value, "same_as_input_stress", "analytic"
        raise ValueError(f"unsupported {model} target: {target}")

    def _solve_peck_or_black(
        self,
        known: Dict[str, float],
        target: str,
        ratio_test: str,
        ratio_use: str,
        exponent: str,
    ) -> Tuple[float, str, str]:
        model = "black_equation" if "current" in ratio_test else "peck"
        common = {
            "acceleration_factor",
            "activation_energy",
            "test_temperature",
            "use_temperature",
        }
        if target == exponent:
            required = common | {ratio_test, ratio_use}
            self._require_exact(known, required, model, target)
            self._positive_keys(known, *required)
            denominator = math.log(known[ratio_test] / known[ratio_use])
            if denominator == 0:
                raise ValueError("equal stress levels cannot identify exponent")
            thermal = known["activation_energy"] / K_B_EV_PER_K * (
                1.0 / known["use_temperature"]
                - 1.0 / known["test_temperature"]
            )
            value = (
                math.log(known["acceleration_factor"]) - thermal
            ) / denominator
            if value < 0:
                raise ValueError("solution implies a negative exponent")
            return value, "dimensionless", "analytic"
        if target == "activation_energy":
            required = {
                "acceleration_factor",
                "test_temperature",
                "use_temperature",
                ratio_test,
                ratio_use,
                exponent,
            }
            self._require_exact(known, required, model, target)
            self._positive_keys(known, *required)
            denominator = (
                1.0 / known["use_temperature"]
                - 1.0 / known["test_temperature"]
            )
            if denominator == 0:
                raise ValueError("equal temperatures cannot identify Ea")
            stress_log = known[exponent] * math.log(
                known[ratio_test] / known[ratio_use]
            )
            value = (
                K_B_EV_PER_K
                * (math.log(known["acceleration_factor"]) - stress_log)
                / denominator
            )
            if value < 0:
                raise ValueError("solution implies a negative activation energy")
            return value, "eV", "analytic"
        raise ValueError(f"unsupported {model} target: {target}")

    def _solve_weibull(
        self,
        known: Dict[str, float],
        target: str,
        request: V3ParameterSolverRequest,
    ) -> Tuple[float, str, str]:
        time_unit = request.units.get("time", "hour")
        if target == "scale":
            quantile_keys = {
                "shape",
                "quantile_probability",
                "quantile_life",
            }
            reliability_keys = {"shape", "time", "reliability"}
            if set(known) == quantile_keys:
                self._validate_probability(known["quantile_probability"], False)
                self._positive_keys(known, "shape", "quantile_life")
                value = known["quantile_life"] / (
                    -math.log(1.0 - known["quantile_probability"])
                ) ** (1.0 / known["shape"])
            elif set(known) == reliability_keys:
                self._validate_probability(known["reliability"], False)
                self._positive_keys(known, "shape", "time")
                value = known["time"] / (
                    -math.log(known["reliability"])
                ) ** (1.0 / known["shape"])
            else:
                raise ValueError(
                    "weibull scale requires shape plus either quantile inputs "
                    "or time and reliability"
                )
            return value, time_unit, "analytic"
        if target == "shape":
            if set(known) == {
                "scale",
                "quantile_probability",
                "quantile_life",
            }:
                self._positive_keys(known, "scale", "quantile_life")
                self._validate_probability(known["quantile_probability"], False)
                denominator = math.log(
                    known["quantile_life"] / known["scale"]
                )
                numerator = math.log(
                    -math.log(1.0 - known["quantile_probability"])
                )
            elif set(known) == {"scale", "time", "reliability"}:
                self._positive_keys(known, "scale", "time")
                self._validate_probability(known["reliability"], False)
                denominator = math.log(known["time"] / known["scale"])
                numerator = math.log(-math.log(known["reliability"]))
            else:
                raise ValueError(
                    "weibull shape requires scale plus quantile inputs or "
                    "time and reliability"
                )
            if denominator == 0:
                raise ValueError("inputs do not identify Weibull shape")
            value = numerator / denominator
            if value <= 0:
                raise ValueError("solution implies non-positive Weibull shape")
            return value, "dimensionless", "analytic"
        if target == "quantile_life":
            self._require_exact(
                known,
                {"scale", "shape", "quantile_probability"},
                "weibull",
                target,
            )
            self._positive_keys(known, "scale", "shape")
            self._validate_probability(known["quantile_probability"], False)
            value = known["scale"] * (
                -math.log(1.0 - known["quantile_probability"])
            ) ** (1.0 / known["shape"])
            return value, time_unit, "analytic"
        if target == "reliability":
            self._require_exact(
                known, {"scale", "shape", "time"}, "weibull", target
            )
            self._positive_keys(known, "scale", "shape")
            if known["time"] < 0:
                raise ValueError("time must be non-negative")
            value = math.exp(
                -((known["time"] / known["scale"]) ** known["shape"])
            )
            return value, "fraction", "analytic"
        if target == "time":
            self._require_exact(
                known,
                {"scale", "shape", "reliability"},
                "weibull",
                target,
            )
            self._positive_keys(known, "scale", "shape")
            self._validate_probability(known["reliability"], False)
            value = known["scale"] * (
                -math.log(known["reliability"])
            ) ** (1.0 / known["shape"])
            return value, time_unit, "analytic"
        raise ValueError(f"unsupported weibull target: {target}")

    def _solve_exponential(
        self,
        known: Dict[str, float],
        target: str,
        request: V3ParameterSolverRequest,
    ) -> Tuple[float, str, str]:
        time_unit = request.units.get("time", "hour")
        if target == "reliability":
            self._require_exact(
                known,
                {"hazard_rate", "time"},
                "exponential_reliability",
                target,
            )
            self._positive_keys(known, "hazard_rate")
            if known["time"] < 0:
                raise ValueError("time must be non-negative")
            return (
                math.exp(-known["hazard_rate"] * known["time"]),
                "fraction",
                "analytic",
            )
        if target in {"hazard_rate", "time"}:
            other = "time" if target == "hazard_rate" else "hazard_rate"
            self._require_exact(
                known,
                {"reliability", other},
                "exponential_reliability",
                target,
            )
            self._validate_probability(known["reliability"], False)
            self._positive_keys(known, other)
            value = -math.log(known["reliability"]) / known[other]
            unit = f"1/{time_unit}" if target == "hazard_rate" else time_unit
            return value, unit, "analytic"
        raise ValueError(f"unsupported exponential target: {target}")

    def _solve_zero_failure(
        self,
        known: Dict[str, float],
        target: str,
        request: V3ParameterSolverRequest,
    ) -> Tuple[float, str, str]:
        if target in {
            "failure_probability_upper",
            "demonstrated_reliability",
        }:
            self._require_exact(
                known,
                {"sample_size", "confidence"},
                "zero_failure_demonstration",
                target,
            )
            n = self._positive_integer(known["sample_size"], "sample_size")
            self._validate_probability(known["confidence"], False)
            reliability = (1.0 - known["confidence"]) ** (1.0 / n)
            value = (
                1.0 - reliability
                if target == "failure_probability_upper"
                else reliability
            )
            return value, "fraction", "analytic_exact_binomial"
        if target == "sample_size":
            self._require_exact(
                known,
                {"target_reliability", "confidence"},
                "zero_failure_demonstration",
                target,
            )
            self._validate_probability(known["target_reliability"], False)
            self._validate_probability(known["confidence"], False)
            value = math.ceil(
                math.log(1.0 - known["confidence"])
                / math.log(known["target_reliability"])
            )
            return float(value), "count", "analytic_exact_binomial"
        if target in {"test_time", "target_rate"}:
            other = "target_rate" if target == "test_time" else "test_time"
            self._require_exact(
                known,
                {other, "sample_size", "confidence"},
                "zero_failure_demonstration",
                target,
            )
            n = self._positive_integer(known["sample_size"], "sample_size")
            self._positive_keys(known, other)
            self._validate_probability(known["confidence"], False)
            value = -math.log(1.0 - known["confidence"]) / (
                n * known[other]
            )
            unit = (
                request.units.get("time", "hour")
                if target == "test_time"
                else f"1/{request.units.get('time', 'hour')}"
            )
            return value, unit, "analytic_poisson_exposure"
        raise ValueError(f"unsupported zero-failure target: {target}")

    def _solve_constant_hazard(
        self,
        known: Dict[str, float],
        target: str,
        request: V3ParameterSolverRequest,
    ) -> Tuple[float, str, str]:
        variables = {"failures", "sample_size", "test_time", "hazard_rate"}
        if target not in variables:
            raise ValueError(f"unsupported constant-hazard target: {target}")
        self._require_exact(
            known, variables - {target}, "constant_hazard_ffr", target
        )
        for key, value in known.items():
            if key == "failures":
                if value < 0 or not float(value).is_integer():
                    raise ValueError("failures must be a non-negative integer")
            else:
                self._positive_keys(known, key)
        if "sample_size" in known:
            n = self._positive_integer(known["sample_size"], "sample_size")
            if "failures" in known and known["failures"] > n:
                raise ValueError("failures cannot exceed sample_size")

        if target == "hazard_rate":
            value = known["failures"] / (
                known["sample_size"] * known["test_time"]
            )
            unit = f"1/{request.units.get('time', 'hour')}"
        elif target == "failures":
            value = (
                known["hazard_rate"]
                * known["sample_size"]
                * known["test_time"]
            )
            unit = "expected_count"
        elif target == "sample_size":
            value = known["failures"] / (
                known["hazard_rate"] * known["test_time"]
            )
            unit = "count"
        else:
            value = known["failures"] / (
                known["hazard_rate"] * known["sample_size"]
            )
            unit = request.units.get("time", "hour")
        return value, unit, "analytic"

    @staticmethod
    def _require_exact(
        known: Dict[str, float],
        expected: Iterable[str],
        model: str,
        target: str,
    ) -> None:
        expected_set = set(expected)
        if set(known) != expected_set:
            raise ValueError(
                f"{model}/{target} known_parameters must be exactly "
                f"{sorted(expected_set)}"
            )

    @staticmethod
    def _positive_keys(known: Dict[str, float], *keys: str) -> None:
        for key in keys:
            value = known[key]
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be finite and greater than zero")

    @staticmethod
    def _positive_integer(value: float, name: str) -> int:
        if value <= 0 or not float(value).is_integer():
            raise ValueError(f"{name} must be a positive integer")
        return int(value)

    @staticmethod
    def _validate_probability(value: float, allow_endpoints: bool) -> None:
        valid = 0 <= value <= 1 if allow_endpoints else 0 < value < 1
        if not valid:
            bounds = "[0, 1]" if allow_endpoints else "(0, 1)"
            raise ValueError(f"probability must be in {bounds}")

    @staticmethod
    def _enforce_constraints(
        value: float, constraints: Dict[str, float]
    ) -> None:
        if "min" in constraints and value < constraints["min"]:
            raise ValueError("solution is below constraint min")
        if "max" in constraints and value > constraints["max"]:
            raise ValueError("solution is above constraint max")

    @staticmethod
    def _bounded_root(function, request: V3ParameterSolverRequest) -> float:
        low = request.constraints.get("min", 1e-9)
        high = request.constraints.get("max", 5000.0)
        if low <= 0 or high <= low:
            raise ValueError("temperature root bounds must satisfy 0 < min < max")
        f_low = function(low)
        f_high = function(high)
        if not math.isfinite(f_low) or not math.isfinite(f_high):
            raise ValueError("root bounds produced a non-finite residual")
        if f_low == 0:
            return low
        if f_high == 0:
            return high
        if f_low * f_high > 0:
            raise ValueError("no solution in the requested bounds")
        return float(
            brentq(
                function,
                low,
                high,
                # The request tolerance qualifies the back-substituted model,
                # not relative error in Kelvin. A loose x tolerance can stop
                # before the original residual/AF accuracy requirement is met.
                # Tighten the numerical solve; never relax the acceptance gate.
                xtol=min(request.tolerance, 1e-12),
                rtol=4 * math.ulp(1.0),
            )
        )

    @staticmethod
    def _safe_exp(log_value: float) -> float:
        if not math.isfinite(log_value) or abs(log_value) > MAX_LOG_FLOAT:
            raise ValueError("acceleration factor exponent is outside safe range")
        value = math.exp(log_value)
        if not math.isfinite(value) or value <= 0:
            raise ValueError("acceleration factor is non-finite or non-positive")
        return value

    @staticmethod
    def _require_finite(value: float, name: str) -> None:
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")

    @staticmethod
    def _require_finite_positive(value: float, name: str) -> None:
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and greater than zero")

    @staticmethod
    def _canonical_units(parameters: Dict[str, float]) -> Dict[str, str]:
        units = {}
        for key in parameters:
            if key == "activation_energy":
                units[key] = "eV"
            elif "temperature" in key:
                units[key] = "K"
            elif "humidity" in key and "exponent" not in key:
                units[key] = "fraction"
            elif key.endswith("_exponent"):
                units[key] = "dimensionless"
            else:
                units[key] = "same_input_unit"
        return units

    @staticmethod
    def _assumptions(model: str) -> List[str]:
        common = [
            "AF is defined as life_use divided by life_test.",
            "Parameters are constant over each declared stress condition.",
        ]
        if model == "multi_stage_equivalent_exposure":
            return [
                "Damage or exposure is linearly additive across stages.",
                "Each stage AF uses life_use divided by life_stage.",
            ]
        if model in {"zero_failure_demonstration", "constant_hazard_ffr"}:
            return [
                "Units have equal exposure unless total exposure is explicit.",
                "Events are independent under the selected probability model.",
            ]
        return common

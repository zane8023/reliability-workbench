"""Transport-neutral JSON dispatcher over the already published calculations.

This module performs no HTTP, file, network, database, or session operations.
The caller supplies a parsed v1 envelope and is responsible for transport limits.
"""
from __future__ import annotations

import json
import math
from typing import Any

from pydantic import BaseModel, ValidationError

from app.services.exponential_fit import fit_exponential
from app.services.fixed_reliability import evaluate_fixed_reliability
from app.services.kaplan_meier import kaplan_meier
from app.services.saved_report import render_saved_report
from app.services.v3_accelerated_solver_service import V3AcceleratedSolverService
from app.services.zero_failure_binomial import zero_failure_upper
from app.validators.exponential_fit import ExponentialFitRequest
from app.validators.fixed_reliability import FixedReliabilityRequest
from app.validators.v3_accelerated_solver import V3AcceleratedLifeEvaluateRequest


CONTRACT_VERSION = "1"
MAX_REQUEST_BYTES = 1_048_576
MAX_OBSERVATIONS = 10_000

_ARRHENIUS_FIELDS = {
    "model_name", "parameters", "temperature_unit", "activation_energy_unit",
    "humidity_unit", "life_conversion",
}
_ARRHENIUS_LIFE_FIELDS = {"input_life", "input_condition", "time_unit"}
_FIXED_FIELDS = {"model", "parameters", "time", "time_unit", "quantile_probability"}
_EXPONENTIAL_FIELDS = {"observations", "time_unit"}
_OBSERVATION_FIELDS = {"kind", "time"}
_KM_FIELDS = {"failures", "right_censored", "time_unit"}
_ZERO_FAILURE_FIELDS = {
    "sample_size", "confidence_level", "event_definition", "observation_window",
}
_REPORT_FIELDS = {"records", "title", "locale"}


def _error(code: str, message: str, fields: list[str] | None = None) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "error": {"code": code, "message": message, "fields": fields or []},
    }


def _unknown_fields(value: Any, allowed: set[str], prefix: str) -> list[str]:
    if not isinstance(value, dict):
        return [prefix or "input"]
    # Never reflect caller-controlled key strings in the response.
    return [prefix or "request"] if any(key not in allowed for key in value) else []


def _reject_boolean_numbers(value: Any, path: str = "input") -> None:
    """JSON booleans must not pass as numeric values through Pydantic coercion."""
    if isinstance(value, bool):
        raise ValueError(f"boolean_not_numeric:{path}")
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_boolean_numbers(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_boolean_numbers(item, f"{path}[{index}]")


def _finite_json(value: Any) -> Any:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    # This both checks that the result is JSON-compatible and rejects NaN/Inf.
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return json.loads(encoded)


def parse_json_body(body: bytes) -> Any:
    """Strictly decode a bounded UTF-8 JSON body; suitable for a future adapter."""
    if not isinstance(body, bytes):
        raise TypeError("body must be bytes")
    if len(body) > MAX_REQUEST_BYTES:
        raise ValueError("request_too_large")

    def reject_constant(_value: str) -> None:
        raise ValueError("non_finite_json_number")

    def finite_float(value: str) -> float:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("non_finite_json_number")
        return number

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    text = body.decode("utf-8", errors="strict")
    return json.loads(text, parse_constant=reject_constant, parse_float=finite_float,
                      object_pairs_hook=unique_object)


def _pydantic_fields(exc: ValidationError) -> list[str]:
    # Nested extra-field locations can contain caller-supplied key names.
    # Keep the response stable and avoid echoing those names.
    del exc
    return []


def _dispatch_calculation(operation: str, data: dict[str, Any]) -> Any:
    if operation == "arrhenius.evaluate":
        unknown = _unknown_fields(data, _ARRHENIUS_FIELDS, "input")
        if unknown:
            raise _InputFieldsError(unknown)
        life = data.get("life_conversion")
        if life is not None:
            unknown = _unknown_fields(life, _ARRHENIUS_LIFE_FIELDS, "input.life_conversion")
            if unknown:
                raise _InputFieldsError(unknown)
        _reject_boolean_numbers(data)
        request = V3AcceleratedLifeEvaluateRequest.model_validate(data, strict=True)
        if request.model_name != "arrhenius":
            raise NotImplementedError
        # Preserve the published service's raw dict result. Do not wrap it in
        # Runtime74's response model or provide internal governance context.
        return V3AcceleratedSolverService().evaluate_acceleration(request)

    if operation == "reliability.evaluate":
        unknown = _unknown_fields(data, _FIXED_FIELDS, "input")
        if unknown:
            raise _InputFieldsError(unknown)
        _reject_boolean_numbers(data)
        return evaluate_fixed_reliability(FixedReliabilityRequest.model_validate(data, strict=True))

    if operation == "exponential.fit":
        unknown = _unknown_fields(data, _EXPONENTIAL_FIELDS, "input")
        if unknown:
            raise _InputFieldsError(unknown)
        observations = data.get("observations")
        if isinstance(observations, list):
            if len(observations) > MAX_OBSERVATIONS:
                raise _InputFieldsError(["input.observations"])
            for index, observation in enumerate(observations):
                bad = _unknown_fields(observation, _OBSERVATION_FIELDS, f"input.observations[{index}]")
                if bad:
                    raise _InputFieldsError(bad)
        _reject_boolean_numbers(data)
        return fit_exponential(ExponentialFitRequest.model_validate(data, strict=True))

    if operation == "kaplan_meier.estimate":
        unknown = _unknown_fields(data, _KM_FIELDS, "input")
        if unknown:
            raise _InputFieldsError(unknown)
        failures = data.get("failures")
        censored = data.get("right_censored", [])
        if not isinstance(failures, list) or not isinstance(censored, list):
            raise _InputFieldsError(["input.failures", "input.right_censored"])
        if len(failures) + len(censored) > MAX_OBSERVATIONS:
            raise _InputFieldsError(["input.failures", "input.right_censored"])
        _reject_boolean_numbers(data)
        if "time_unit" not in data:
            raise _InputFieldsError(["input.time_unit"])
        return kaplan_meier(failures, censored, time_unit=data["time_unit"])

    if operation == "zero_failure.upper_bound":
        unknown = _unknown_fields(data, _ZERO_FAILURE_FIELDS, "input")
        if unknown:
            raise _InputFieldsError(unknown)
        _reject_boolean_numbers(data)
        missing = sorted(_ZERO_FAILURE_FIELDS - set(data))
        if missing:
            raise _InputFieldsError([f"input.{name}" for name in missing])
        return zero_failure_upper(
            data["sample_size"], data["confidence_level"],
            event_definition=data["event_definition"],
            observation_window=data["observation_window"],
        )

    if operation == "report.render_saved":
        unknown = _unknown_fields(data, _REPORT_FIELDS, "input")
        if unknown:
            raise _InputFieldsError(unknown)
        # The published renderer has its own JSON, record-count, locale and
        # selected-field validation. It does not invoke a calculator or write.
        kwargs = {}
        if "title" in data:
            kwargs["title"] = data["title"]
        if "locale" in data:
            kwargs["locale"] = data["locale"]
        return render_saved_report(data.get("records"), **kwargs)

    raise _UnknownOperationError


class _InputFieldsError(Exception):
    def __init__(self, fields: list[str]):
        self.fields = fields


class _UnknownOperationError(Exception):
    pass


def dispatch(operation: str, envelope: Any) -> dict[str, Any]:
    """Dispatch one already-parsed v1 request and return a stable envelope.

    This is a pure in-process adapter; it has no HTTP semantics or persistence.
    A future transport should call parse_json_body first and map error codes to
    status codes without logging or echoing the request body.
    """
    if not isinstance(operation, str) or operation not in {
        "arrhenius.evaluate", "reliability.evaluate", "exponential.fit",
        "kaplan_meier.estimate", "zero_failure.upper_bound", "report.render_saved",
    }:
        return _error("unknown_operation", "Operation is not available.")
    if not isinstance(envelope, dict):
        return _error("invalid_request", "Request must be a JSON object.")
    unknown = _unknown_fields(envelope, {"contract_version", "input"}, "")
    if unknown:
        return _error("invalid_request", "Request contains unsupported fields.", unknown)
    if envelope.get("contract_version") != CONTRACT_VERSION:
        return _error("unsupported_contract_version", "Contract version is not supported.", ["contract_version"])
    data = envelope.get("input")
    if not isinstance(data, dict):
        return _error("invalid_request", "Input must be a JSON object.", ["input"])
    try:
        result = _dispatch_calculation(operation, data)
        result = _finite_json(result)
        response = {"contract_version": CONTRACT_VERSION, "result": result}
        _finite_json(response)
        return response
    except _UnknownOperationError:
        return _error("unknown_operation", "Operation is not available.")
    except _InputFieldsError as exc:
        return _error("invalid_input", "Input fields are missing or unsupported.", exc.fields)
    except ValidationError as exc:
        return _error("invalid_input", "Input validation failed.", _pydantic_fields(exc))
    except NotImplementedError:
        return _error("unsupported_model", "This model is not available in the public preview.")
    except ValueError:
        return _error("invalid_input", "Input is invalid for this operation.")
    except (TypeError, OverflowError):
        return _error("invalid_input", "Input cannot be represented by this operation.")
    except Exception:
        # Do not return exception text, traceback, filesystem paths, or inputs.
        return _error("internal_error", "The operation could not be completed.")


"""Fixed-parameter Weibull and exponential reliability preview.

Adapted from the project reliability metrics implementation: narrowed to R, F,
h and quantile, with stable failure probabilities and explicit finite limits.
"""
import math
import sys
from app.validators.fixed_reliability import FixedReliabilityRequest, FixedReliabilityResult


def evaluate_fixed_reliability(request: FixedReliabilityRequest) -> FixedReliabilityResult:
    """Evaluate supplied parameters; does not fit data or forecast field risk."""
    request = FixedReliabilityRequest.model_validate(request.model_dump())
    t = request.time
    params = request.parameters
    p = request.quantile_probability
    warnings = []
    try:
        if request.model == "weibull":
            scale, shape = params["scale"], params["shape"]
            if t == 0:
                cumulative_hazard = 0.0
                hazard = None if shape < 1 else (1.0 / scale if shape == 1 else 0.0)
                if hazard is None:
                    warnings.append("Weibull hazard is singular at time zero for shape below one.")
            else:
                difference = t - scale
                # Close values lose their relative difference when logarithms
                # are subtracted; the branch also bounds division by scale.
                if abs(difference) <= 0.5 * scale:
                    log_ratio = math.log1p(difference / scale)
                else:
                    log_ratio = math.log(t) - math.log(scale)
                log_cumulative = shape * log_ratio
                cumulative_hazard = (math.inf if log_cumulative > math.log(sys.float_info.max)
                                     else math.exp(log_cumulative))
                log_hazard = math.log(shape) - math.log(scale) + (shape - 1.0) * log_ratio
                if log_hazard > math.log(sys.float_info.max):
                    raise ValueError("hazard exceeds floating-point range")
                hazard = math.exp(log_hazard)
            # Keep the complete quantile in log space so an intermediate
            # power cannot underflow before a large scale rescues the result.
            log_quantile = math.log(scale) + math.log(-math.log1p(-p)) / shape
            quantile = math.exp(log_quantile)
            reference = "https://www.itl.nist.gov/div898/handbook/apr/section1/apr162.htm"
        else:
            rate = params["failure_rate"]
            cumulative_hazard = rate * t
            hazard = rate
            quantile = -math.log1p(-p) / rate
            reference = "https://www.itl.nist.gov/div898/handbook/apr/section1/apr161.htm"
        reliability = math.exp(-cumulative_hazard)
        failure = -math.expm1(-cumulative_hazard)
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("calculation exceeds floating-point range") from exc
    if (not all(math.isfinite(x) for x in (reliability, failure, quantile))
            or quantile <= 0
            or (hazard is not None and not math.isfinite(hazard))):
        raise ValueError("calculation exceeds floating-point range")
    return FixedReliabilityResult(
        model=request.model, parameters=params, time=t, time_unit=request.time_unit,
        reliability=reliability, failure_probability=failure, hazard_rate=hazard,
        hazard_unit=f"1/{request.time_unit}", quantile_probability=p, quantile_time=quantile,
        validation_status="synthetic_case_checked",
        validation_scope="Fixed-parameter synthetic checks only; no fitting, calibration or field-risk validation.",
        provenance={"formula_reference_for_comparison": reference,
                    "inputs": "User-supplied parameters; no evidence of suitability or calibration is assumed."},
        warnings=warnings,
    )

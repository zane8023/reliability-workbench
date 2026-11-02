"""Exponential point MLE for exact failures and right-censored records.

New narrow implementation using the exponential likelihood relationship; it
is not a direct export of the original multi-model fitting engine.
"""
import math
from app.validators.exponential_fit import ExponentialFitRequest, ExponentialFitResult


def fit_exponential(request: ExponentialFitRequest) -> ExponentialFitResult:
    """Estimate rate and scale under IID exponential and independent censoring assumptions."""
    request = ExponentialFitRequest.model_validate(request.model_dump())
    observations = request.observations
    failures = sum(item.kind == "exact" for item in observations)
    if failures == 0:
        raise ValueError("no observed failures: a finite positive point MLE is not identifiable")
    max_time = max(item.time for item in observations)
    scaled_sum = math.fsum(item.time / max_time for item in observations)
    try:
        scale = max_time * (scaled_sum / failures)
        rate = (failures / scaled_sum) / max_time
        total = max_time * scaled_sum
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("point estimate exceeds floating-point range") from exc
    if not math.isfinite(scale) or not math.isfinite(rate) or scale <= 0 or rate <= 0:
        raise ValueError("point estimate exceeds floating-point range")
    warnings = [
        "A numerical estimate does not establish the exponential model or independent censoring.",
        "No confidence interval, uncertainty estimate, or market prediction is provided.",
    ]
    if failures < 5:
        warnings.append("Fewer than five observed failures: precision may be poor and evidence limited.")
    if not math.isfinite(total):
        total = None
        warnings.append("Total exposure exceeds floating-point range; use the scaled representation.")
    return ExponentialFitResult(
        model="exponential", method="maximum_likelihood_point_estimate",
        sample_count=len(observations), failure_count=failures,
        right_censored_count=len(observations) - failures,
        total_exposure=total, exposure_scale=max_time, exposure_scaled_sum=scaled_sum,
        time_unit=request.time_unit, failure_rate=rate, failure_rate_unit=f"1/{request.time_unit}",
        scale=scale, validation_status="synthetic_case_checked",
        validation_scope="Exact failures and right-censored records only; point estimate, not model or field validation.",
        assumptions=["Independent identically distributed exponential lifetimes with constant hazard.",
                     "Independent, non-informative right censoring; one record per unit, no delayed entry."],
        warnings=warnings,
        provenance={"formula_reference_for_comparison": "https://www.itl.nist.gov/div898/handbook/apr/section4/apr412.htm",
                    "inputs": "User-supplied observations; no source or model suitability has been verified."},
    )

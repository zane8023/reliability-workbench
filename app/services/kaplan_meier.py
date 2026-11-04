"""Kaplan–Meier point estimates for exact failures and right censoring.

Adapted from the event/risk-set calculation in the original nonparametric
service. Confidence intervals and internal service dependencies are omitted.
"""
import math


def kaplan_meier(failures, right_censored=(), *, time_unit):
    """Return one row per failure time, with failures before tied censoring."""
    if not isinstance(time_unit, str) or not time_unit.strip():
        raise ValueError("time_unit must be a non-empty string")
    def validate(values):
        if not isinstance(values, (list, tuple)):
            raise ValueError("observations must be lists or tuples")
        result = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("times must be finite non-negative numbers")
            original = value
            try:
                value = float(value)
            except OverflowError as exc:
                raise ValueError("time is out of range") from exc
            if isinstance(original, int) and math.isfinite(value) and int(value) != original:
                raise ValueError("integer time cannot be represented exactly")
            if not math.isfinite(value) or value < 0:
                raise ValueError("times must be finite non-negative numbers")
            result.append(value)
        return sorted(result)
    failed, censored = validate(failures), validate(right_censored)
    if not failed and not censored:
        raise ValueError("at least one observation is required")
    from collections import Counter
    events, cens = Counter(failed), Counter(censored)
    risk, survival, rows = len(failed) + len(censored), 1.0, []
    for time in sorted(set(events) | set(cens)):
        count = events[time]
        if count:
            survival *= 1.0 - count / risk
            rows.append({"time": time, "at_risk": risk, "failures": count,
                         "censored_at_time": cens[time], "survival": survival})
        risk -= count + cens[time]
    return {"model": "Kaplan-Meier", "time_unit": time_unit.strip(),
            "sample_count": len(failed) + len(censored), "failure_count": len(failed),
            "right_censored_count": len(censored),
            "last_observation_time": max(failed + censored), "rows": rows,
            "validation_status": "synthetic_case_checked",
            "limitations": ["Independent non-informative right censoring is assumed.",
                            "Point estimates only; no confidence interval, delayed entry or extrapolation beyond observation."]}

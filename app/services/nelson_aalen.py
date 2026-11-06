"""Local point-estimate experiment based on the published KM risk-set rows.

This is not the original full nonparametric service and provides no interval.
"""
import math

from app.services.kaplan_meier import kaplan_meier

MAX_OBSERVATIONS = 10000
UNITS = ("second", "minute", "hour", "day", "year")


def nelson_aalen_point(failures, right_censored=(), *, time_unit):
    """Estimate H(t)=sum(d/n) at event times, with tied censoring still at risk.

    Positive times and at least one failure are preview quality gates, not
    universal mathematical requirements. Caller validates scientific use.
    """
    if type(time_unit) is not str or time_unit not in UNITS:
        raise ValueError("unsupported time unit")
    if not isinstance(failures, (list, tuple)) or not isinstance(right_censored, (list, tuple)):
        raise ValueError("observations must be lists or tuples")
    if len(failures) + len(right_censored) > MAX_OBSERVATIONS:
        raise ValueError("observation limit exceeded")
    if not failures:
        raise ValueError("at least one exact failure is required in this preview")
    for value in (*failures, *right_censored):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("times must be finite positive numbers")
        try:
            converted = float(value)
        except OverflowError as exc:
            raise ValueError("time is out of range") from exc
        if not math.isfinite(converted) or converted <= 0:
            raise ValueError("times must be finite positive numbers")
        if isinstance(value, int) and int(converted) != value:
            raise ValueError("integer time cannot be represented exactly")

    risk_table = kaplan_meier(failures, right_censored, time_unit=time_unit)
    total = 0.0
    compensation = 0.0
    rows = []
    for item in risk_table["rows"]:
        increment = item["failures"] / item["at_risk"]
        corrected = increment - compensation
        updated = total + corrected
        compensation = (updated - total) - corrected
        total = updated
        rows.append({"time": item["time"], "at_risk": item["at_risk"], "failures": item["failures"],
                     "censored_at_time": item["censored_at_time"], "cumulative_hazard": total})
    return {
        "model": "Nelson-Aalen",
        "time_unit": time_unit,
        "sample_count": risk_table["sample_count"],
        "failure_count": risk_table["failure_count"],
        "right_censored_count": risk_table["right_censored_count"],
        "last_observation_time": risk_table["last_observation_time"],
        "rows": rows,
        "validation_status": "synthetic_case_checked",
        "assumptions": ["One observation per unit and independent non-informative right censoring are assumed."],
        "limitations": ["Point estimates only; no confidence interval, delayed entry or extrapolation.",
                        "Cumulative hazard is not a Kaplan-Meier survival estimate.",
                        "Tied failures are grouped as d/n; other tie conventions may differ.",
                        "Inputs and censoring assumptions are not independently validated.",
                        "Binary floating-point inputs may already have been rounded.",
                        "Positive time and at least one failure are preview quality gates."],
        "provenance": {"method_reference": "https://pmc.ncbi.nlm.nih.gov/articles/PMC4617278/",
                       "risk_sets": "Adapted through the published Kaplan-Meier risk-set rows; not the original full service."},
    }

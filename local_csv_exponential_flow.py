"""Experimental in-process CSV -> exponential estimate -> HTML summary."""
import json

from app.services.exponential_fit import fit_exponential
from app.services.saved_report import render_saved_report
from app.validators.exponential_fit import ExponentialFitRequest
from local_lifetime_csv_candidate import parse_observations


def _error(code):
    return {"ok": False, "error": {"code": code}}


def analyze_csv(raw, time_unit, locale):
    """Return an in-memory result; no path, listener, access control or storage."""
    try:
        return _analyze(raw, time_unit, locale)
    except MemoryError:
        raise
    except Exception:
        return _error("INTERNAL_ERROR")


def _analyze(raw, time_unit, locale):
    if type(locale) is not str or locale not in ("en", "zh-CN"):
        return _error("INVALID_LOCALE")
    parsed = parse_observations(raw, time_unit)
    if not parsed["ok"]:
        return parsed
    observations = parsed["request"]["observations"]
    if not any(item["kind"] == "exact" for item in observations):
        return _error("NO_OBSERVED_FAILURES")
    try:
        request = ExponentialFitRequest.model_validate(parsed["request"], strict=True)
        result = fit_exponential(request).model_dump(mode="json")
        report = render_saved_report([{"kind": "exponential_fit", "data": result}], locale=locale)
        answer = {
            "ok": True,
            "locale": locale,
            "normalized_request": request.model_dump(mode="json"),
            "result": result,
            "report": report,
            "limitations": parsed["limitations"] + [
                "Exponential point estimate only; no confidence interval or field forecast.",
                "Report is a selected-field HTML summary, not a complete archival record.",
                "This in-process experiment provides no persistence, authentication, or multi-user isolation.",
            ],
        }
        json.dumps(answer, ensure_ascii=False, allow_nan=False)
        return answer
    except (ValueError, TypeError, OverflowError):
        return _error("FIT_OR_REPORT_FAILED")

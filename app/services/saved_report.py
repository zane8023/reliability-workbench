"""Offline display of previously supplied results; no calculation or file I/O.

The asset wrapper and escaped-table presentation are adapted from the project's
EW stored-result renderer. Only explicitly listed fields enter the report.
"""
import base64
import hashlib
from html import escape
import json
import math
import sys
import unicodedata

MAX_BYTES = 8 * 1024 * 1024
MAX_INPUT_BYTES = 256 * 1024

# This helper preserves the original renderer's asset envelope; the original
# store-dependent require() is replaced by a local check.
def asset(name, mime, raw, **metadata):
    if len(raw) > MAX_BYTES:
        raise ValueError("REPORT_ASSET_SIZE_EXCEEDED")
    sha = hashlib.sha256(raw).hexdigest()
    return dict(asset_ref=name + '-' + sha[:24], mime_type=mime, byte_size=len(raw), sha256=sha,
                content_base64=base64.b64encode(raw).decode(), **metadata)

_FIELDS = {
    "arrhenius": ("model_name", "canonical_parameters", "canonical_units", "acceleration_factor",
                   "converted_life", "formula_validation_status", "validation_scope", "warnings"),
    "fixed_reliability": ("model", "parameters", "time", "time_unit", "reliability",
                          "failure_probability", "hazard_rate", "hazard_unit", "quantile_probability",
                          "quantile_time", "validation_status", "validation_scope", "warnings"),
    "exponential_fit": ("model", "method", "sample_count", "failure_count", "right_censored_count",
                        "total_exposure", "exposure_scale", "exposure_scaled_sum", "time_unit",
                        "failure_rate", "failure_rate_unit", "scale", "validation_status",
                        "validation_scope", "assumptions", "warnings"),
    "kaplan_meier": ("model", "time_unit", "sample_count", "failure_count", "right_censored_count",
                     "last_observation_time", "rows", "validation_status", "limitations"),
    "zero_failure_binomial": ("method", "failure_count", "sample_size", "confidence_level",
                              "failure_probability_upper", "event_definition", "observation_window",
                              "validation_status", "assumptions", "limitations"),
}
_NUMBERS = {
    "arrhenius": ("acceleration_factor",),
    "fixed_reliability": ("time", "reliability", "failure_probability", "quantile_probability", "quantile_time"),
    "exponential_fit": ("sample_count", "failure_count", "right_censored_count", "exposure_scale",
                        "exposure_scaled_sum", "failure_rate", "scale"),
    "kaplan_meier": ("last_observation_time",),
    "zero_failure_binomial": ("confidence_level", "failure_probability_upper"),
}
_FIELD_ZH = {
    "model_name": "模型", "model": "模型", "canonical_parameters": "标准化参数",
    "canonical_units": "标准化单位", "acceleration_factor": "加速因子", "converted_life": "寿命换算",
    "formula_validation_status": "验证状态", "validation_status": "验证状态", "validation_scope": "验证范围",
    "warnings": "提示", "parameters": "参数", "time": "时间", "time_unit": "时间单位",
    "reliability": "可靠度", "failure_probability": "失效概率", "hazard_rate": "风险率",
    "hazard_unit": "风险率单位", "quantile_probability": "分位失效概率", "quantile_time": "分位寿命",
    "method": "方法", "sample_count": "样本数", "failure_count": "失效数",
    "right_censored_count": "右删失数", "total_exposure": "总暴露时间", "exposure_scale": "暴露归一化尺度",
    "exposure_scaled_sum": "暴露归一化和", "failure_rate": "失效率", "failure_rate_unit": "失效率单位",
    "scale": "寿命尺度", "assumptions": "假设",
    "last_observation_time": "最后观测时间", "rows": "失效时点记录", "limitations": "限制",
    "sample_size": "试验样本数", "confidence_level": "单侧置信水平",
    "failure_probability_upper": "失效概率单侧上限", "event_definition": "事件定义",
    "observation_window": "观测窗口",
}
_KIND_ZH = {"arrhenius": "Arrhenius 加速", "fixed_reliability": "给定参数可靠性",
            "exponential_fit": "指数分布点估计", "kaplan_meier": "Kaplan–Meier 生存率点估计",
            "zero_failure_binomial": "零失效二项概率上限（实验性）"}

_LABELS = {
    "en": {"title": "Reliability review", "inputs": "Stored result and declared inputs",
           "notice": "Display only. User-supplied results and model assumptions are not independently validated.",
           "charts": "No chart is included in this preview.", "scope": "Scope and warnings"},
    "zh-CN": {"title": "可靠性分析复核", "inputs": "已保存结果与声明的输入",
              "notice": "仅供展示。用户提供的结果及模型假设未经本报告独立验证。",
              "charts": "本预览暂不包含图表。", "scope": "范围与提示"},
}


def _finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _count(value, *, minimum=0, maximum=None):
    return (type(value) is int and _finite_number(value) and value >= minimum
            and (maximum is None or value <= maximum))


def _text_list(value):
    return (isinstance(value, list) and bool(value)
            and all(isinstance(item, str) and item.strip() for item in value))


def _validate_survival_record(kind, data):
    """Check display shape and ranges, not estimator arithmetic or suitability."""
    if not _text_list(data["limitations"]):
        raise ValueError("stored limitations must be a non-empty list of text")
    if kind == "kaplan_meier":
        if data["model"] != "Kaplan-Meier":
            raise ValueError("stored model does not match kind")
        if not isinstance(data["time_unit"], str) or not data["time_unit"].strip():
            raise ValueError("stored time unit is required")
        n, failed, censored = (data[key] for key in ("sample_count", "failure_count", "right_censored_count"))
        if not (_count(n, minimum=1) and _count(failed) and _count(censored)
                and failed + censored == n):
            raise ValueError("stored observation counts are inconsistent")
        if data["last_observation_time"] < 0:
            raise ValueError("stored observation time must be non-negative")
        rows = data["rows"]
        if not isinstance(rows, list):
            raise ValueError("stored failure-time rows must be a list")
        fields = {"time", "at_risk", "failures", "censored_at_time", "survival"}
        previous_time = -1.0
        failures_in_rows = 0
        for row in rows:
            if not isinstance(row, dict) or set(row) != fields:
                raise ValueError("stored failure-time row fields do not match the display contract")
            if (not _finite_number(row["time"]) or not previous_time < row["time"] <= data["last_observation_time"]
                    or row["time"] < 0 or not _finite_number(row["survival"])
                    or not 0 <= row["survival"] <= 1):
                raise ValueError("stored failure-time row values are outside their ranges")
            if not (_count(row["at_risk"], minimum=1, maximum=n)
                    and _count(row["failures"], minimum=1, maximum=row["at_risk"])
                    and _count(row["censored_at_time"], maximum=row["at_risk"] - row["failures"])):
                raise ValueError("stored failure-time row counts are invalid")
            previous_time = row["time"]
            failures_in_rows += row["failures"]
        if failures_in_rows != failed:
            raise ValueError("stored failure count does not match the failure-time rows")
    else:
        if data["method"] != "exact_one_sided_binomial":
            raise ValueError("stored method does not match kind")
        if not _count(data["failure_count"], maximum=0) or not _count(data["sample_size"], minimum=1, maximum=10_000_000):
            raise ValueError("stored zero-failure counts are outside preview scope")
        if not 0 < data["confidence_level"] < 1 or not sys.float_info.min <= data["failure_probability_upper"] <= 1:
            raise ValueError("stored zero-failure probabilities are outside preview scope")
        for key in ("event_definition", "observation_window"):
            value = data[key]
            if (not isinstance(value, str) or len(value) > 500
                    or not any(not char.isspace() and not unicodedata.category(char).startswith("C") for char in value)):
                raise ValueError("stored event and window labels must contain meaningful text of at most 500 characters")
        if not _text_list(data["assumptions"]):
            raise ValueError("stored assumptions must be a non-empty list of text")


def render_saved_report(records, *, title=None, locale="en"):
    """Render selected fields from stored dictionaries without invoking solvers.

    The returned asset contains base64 HTML bytes. This function never opens or
    writes a file. Callers choose explicitly where to save the decoded bytes.
    """
    if locale not in _LABELS:
        raise ValueError("unsupported locale")
    if title is None:
        title = _LABELS[locale]["title"]
    if not isinstance(title, str) or not title or len(title) > 160:
        raise ValueError("title must contain 1 to 160 characters")
    try:
        title.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("title must be valid UTF-8 text") from exc
    if not isinstance(records, list) or not 1 <= len(records) <= 25:
        raise ValueError("provide between 1 and 25 stored records")
    try:
        payload = json.dumps(records, ensure_ascii=False, sort_keys=True, allow_nan=False)
        payload_bytes = payload.encode("utf-8")
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
        raise ValueError("stored records must contain finite JSON data") from exc
    if len(payload_bytes) > MAX_INPUT_BYTES:
        raise ValueError("stored records exceed size limit")
    sections = []
    for item in records:
        if not isinstance(item, dict) or set(item) != {"kind", "data"}:
            raise ValueError("each stored record requires only kind and data")
        kind, data = item["kind"], item["data"]
        if not isinstance(kind, str) or kind not in _FIELDS or not isinstance(data, dict):
            raise ValueError("unsupported stored result kind")
        missing = [key for key in _FIELDS[kind] if key not in data]
        if missing:
            raise ValueError("stored result missing required fields: " + ", ".join(missing))
        if kind == "arrhenius" and data["model_name"] != "arrhenius":
            raise ValueError("stored model does not match kind")
        if kind == "fixed_reliability" and data["model"] not in ("weibull", "exponential"):
            raise ValueError("stored model does not match kind")
        if kind == "exponential_fit" and data["model"] != "exponential":
            raise ValueError("stored model does not match kind")
        status_key = "formula_validation_status" if kind == "arrhenius" else "validation_status"
        expected_status = ("experimental_synthetic_checks_only" if kind == "zero_failure_binomial"
                           else "synthetic_case_checked")
        if data[status_key] != expected_status:
            raise ValueError("stored validation status is outside preview scope")
        for key in _NUMBERS[kind]:
            value = data[key]
            if not _finite_number(value):
                raise ValueError("stored numeric fields must be finite")
        optional_numeric = ("hazard_rate",) if kind == "fixed_reliability" else ("total_exposure",) if kind == "exponential_fit" else ()
        for key in optional_numeric:
            value = data[key]
            if value is not None and not _finite_number(value):
                raise ValueError("optional numeric fields must be finite or null")
        parameter_key = "canonical_parameters" if kind == "arrhenius" else "parameters" if kind == "fixed_reliability" else None
        if parameter_key:
            parameters = data[parameter_key]
            if not isinstance(parameters, dict) or not parameters or not all(
                isinstance(k, str) and _finite_number(v)
                for k, v in parameters.items()
            ):
                raise ValueError("stored model parameters must be finite numbers")
        if kind == "arrhenius" and not isinstance(data["canonical_units"], dict):
            raise ValueError("canonical units must be an object")
        if kind == "arrhenius" and data["converted_life"] is not None:
            life = data["converted_life"]
            if not isinstance(life, dict) or set(life) != {"value", "condition", "unit"} or not _finite_number(life["value"]):
                raise ValueError("converted life must include a finite value, condition and unit")
        if "validation_scope" in _FIELDS[kind] and (not isinstance(data["validation_scope"], str) or not data["validation_scope"]):
            raise ValueError("stored validation scope is required")
        if "warnings" in _FIELDS[kind] and (not isinstance(data["warnings"], list) or not all(isinstance(v, str) for v in data["warnings"])):
            raise ValueError("stored warnings must be a list of text")
        if kind in ("kaplan_meier", "zero_failure_binomial"):
            _validate_survival_record(kind, data)
        selected = {key: data[key] for key in _FIELDS[kind]}
        rows = "".join("<tr><th>" + escape(_FIELD_ZH.get(key, key) if locale == "zh-CN" else key) + "</th><td><pre>" +
                       escape(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)) +
                       "</pre></td></tr>" for key, value in selected.items())
        display_kind = _KIND_ZH[kind] if locale == "zh-CN" else kind
        sections.append("<section><h2>" + escape(display_kind) + "</h2><table>" + rows + "</table></section>")
    labels = _LABELS[locale]
    html = ("<!doctype html><html lang=\"" + escape(locale, quote=True) +
        "\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">" +
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">" +
        "<title>" + escape(title) + "</title><style>body{font:16px/1.6 system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#233041}table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #dfe4ea;text-align:left;vertical-align:top;padding:.5rem}th{width:30%}pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:0}</style></head><body>" +
        "<h1>" + escape(title) + "</h1><p>" + escape(labels["notice"]) + "</p><h2>" +
        escape(labels["inputs"]) + "</h2>" + "".join(sections) + "<p>" + escape(labels["charts"]) +
        "</p></body></html>").encode("utf-8")
    return asset("saved-report", "text/html", html, presentation_only=True,
                 calculation_performed=False, chart_included=False)

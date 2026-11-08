"""Render caller-declared synthetic result points as a standalone SVG scatter plot.

This is presentation only: it does not fit, interpolate, forecast, or recalculate.
"""
from __future__ import annotations

from fractions import Fraction
import math
import xml.etree.ElementTree as ET
from typing import Any

from app.services.saved_report import asset


SVG_NS = "http://www.w3.org/2000/svg"

WIDTH = 720
HEIGHT = 500
MAX_POINTS = 100
_TOP_FIELDS = {"data_origin", "title", "estimand", "x_axis", "y_axis", "points"}
_AXIS_FIELDS = {"label", "unit"}
_POINT_FIELDS = {"x", "y", "label"}


def _fields(value: Any, allowed: set[str], name: str, required: set[str]) -> dict[str, Any]:
    if type(value) is not dict or not required.issubset(value) or not set(value).issubset(allowed):
        raise ValueError(f"{name}_fields_invalid")
    return value


def _label(value: Any, name: str, maximum: int) -> str:
    if type(value) is not str:
        raise ValueError(f"{name}_invalid")
    value = value.strip()
    if not value or len(value) > maximum or any(not _xml_char(ord(char)) for char in value):
        raise ValueError(f"{name}_invalid")
    return value


def _xml_char(codepoint: int) -> bool:
    return codepoint in (9, 10, 13) or 0x20 <= codepoint <= 0xD7FF or 0xE000 <= codepoint <= 0xFFFD or 0x10000 <= codepoint <= 0x10FFFF


def _number(value: Any, name: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{name}_invalid")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name}_invalid") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name}_invalid")
    return result


def _fraction(value: float, low: float, high: float) -> float:
    if low == high:
        return 0.5
    span = high - low
    if math.isfinite(span) and span != 0.0:
        result = (value - low) / span
    else:
        scale = max(abs(low), abs(high))
        scaled_low, scaled_high, scaled_value = low / scale, high / scale, value / scale
        result = (scaled_value - scaled_low) / (scaled_high - scaled_low)
    return min(1.0, max(0.0, result))


def _interpolate(low: float, high: float, fraction: float) -> float:
    # Avoid cancellation at exact endpoints with very asymmetric bounds.
    if fraction == 0.0:
        return low
    if fraction == 1.0:
        return high
    # Only the five axis ticks (exact multiples of 1/4) call this helper.
    # Keep arithmetic exact until the final binary64 rounding, including
    # cancellation, subnormal values and spans larger than the float limit.
    lower = Fraction(low)
    return float(lower + (Fraction(high) - lower) * Fraction(fraction))


def _fmt(value: float) -> str:
    return "0" if value == 0 else format(value, ".5g")


def _element(parent: ET.Element, name: str, attrs: dict[str, str] | None = None, text: str | None = None) -> ET.Element:
    node = ET.SubElement(parent, f"{{{SVG_NS}}}{name}", attrs or {})
    if text is not None:
        node.text = text
    return node


def render_synthetic_result_scatter(payload: Any) -> dict[str, Any]:
    """Return an SVG asset for one caller-declared synthetic point series.

    The ``data_origin`` marker is an assertion from the caller, not provenance
    verification. All values on each axis share the single declared unit.
    """
    data = _fields(payload, _TOP_FIELDS, "request", _TOP_FIELDS)
    if type(data["data_origin"]) is not str or data["data_origin"] != "synthetic":
        raise ValueError("synthetic_data_required")
    title = _label(data["title"], "title", 120)
    estimand = _label(data["estimand"], "estimand", 100)
    axes: dict[str, tuple[str, str]] = {}
    for key in ("x_axis", "y_axis"):
        axis = _fields(data[key], _AXIS_FIELDS, key, _AXIS_FIELDS)
        axes[key] = (_label(axis["label"], f"{key}_label", 80), _label(axis["unit"], f"{key}_unit", 40))

    points_raw = data["points"]
    if type(points_raw) is not list or not 1 <= len(points_raw) <= MAX_POINTS:
        raise ValueError("point_count_invalid")
    points = []
    for index, raw_point in enumerate(points_raw, start=1):
        point = _fields(raw_point, _POINT_FIELDS, "point", {"x", "y"})
        x = _number(point["x"], "x")
        y = _number(point["y"], "y")
        label = _label(point["label"], "point_label", 80) if "label" in point else f"Point {index}"
        points.append((x, y, label))

    x_unit, y_unit = axes["x_axis"][1], axes["y_axis"][1]
    x_values = [item[0] for item in points]
    y_values = [item[1] for item in points]
    x_low, x_high = min(x_values), max(x_values)
    y_low, y_high = min(y_values), max(y_values)

    left, right, top, bottom = 92.0, 690.0, 94.0, 374.0
    root = ET.Element(f"{{{SVG_NS}}}svg", {
        "width": str(WIDTH), "height": str(HEIGHT), "viewBox": f"0 0 {WIDTH} {HEIGHT}",
        "role": "img", "aria-labelledby": "plot-title plot-description",
    })
    _element(root, "title", {"id": "plot-title"}, title)
    _element(root, "desc", {"id": "plot-description"},
             f"Caller-declared synthetic data; origin not independently verified. Scatter points only for {estimand}; no fitted curve, probability plot, interpolation, or forecast.")
    _element(root, "rect", {"x": "0", "y": "0", "width": str(WIDTH), "height": str(HEIGHT), "fill": "#ffffff"})
    _element(root, "text", {"x": "24", "y": "30", "font-size": "18", "font-weight": "bold", "fill": "#172b4d"}, title)
    _element(root, "text", {"x": "24", "y": "52", "font-size": "11", "fill": "#52657a"},
             "Synthetic demo data (caller-declared; not independently verified) · scatter only · no fit or forecast")

    for tick_index in range(5):
        fraction = tick_index / 4
        x = left + (right - left) * fraction
        y = bottom - (bottom - top) * fraction
        x_value = _interpolate(x_low, x_high, fraction)
        # Use the same low-to-high mapping as the point coordinates below.
        y_value = _interpolate(y_low, y_high, fraction)
        _element(root, "line", {"x1": str(x), "y1": str(top), "x2": str(x), "y2": str(bottom), "stroke": "#e3e9ef", "stroke-width": "1"})
        _element(root, "line", {"x1": str(left), "y1": str(y), "x2": str(right), "y2": str(y), "stroke": "#e3e9ef", "stroke-width": "1"})
        _element(root, "text", {"x": str(x), "y": str(bottom + 22), "text-anchor": "middle", "font-size": "10", "fill": "#52657a"}, _fmt(x_value))
        _element(root, "text", {"x": str(left - 10), "y": str(y + 4), "text-anchor": "end", "font-size": "10", "fill": "#52657a"}, _fmt(y_value))

    _element(root, "line", {"x1": str(left), "y1": str(bottom), "x2": str(right), "y2": str(bottom), "stroke": "#334e68", "stroke-width": "1.5"})
    _element(root, "line", {"x1": str(left), "y1": str(top), "x2": str(left), "y2": str(bottom), "stroke": "#334e68", "stroke-width": "1.5"})
    _element(root, "text", {"x": str((left + right) / 2), "y": "426", "text-anchor": "middle", "font-size": "12", "fill": "#172b4d"}, f"{axes['x_axis'][0]} ({x_unit})")
    _element(root, "text", {"x": "20", "y": str((top + bottom) / 2), "transform": f"rotate(-90 20 {(top + bottom) / 2})", "text-anchor": "middle", "font-size": "12", "fill": "#172b4d"}, f"{axes['y_axis'][0]} ({y_unit})")
    _element(root, "text", {"x": "24", "y": "474", "font-size": "11", "fill": "#52657a"}, f"Estimand: {estimand} · {len(points)} point(s)")

    for x_value, y_value, label in points:
        cx = left + _fraction(x_value, x_low, x_high) * (right - left)
        cy = bottom - _fraction(y_value, y_low, y_high) * (bottom - top)
        circle = _element(root, "circle", {"cx": format(cx, ".6f"), "cy": format(cy, ".6f"), "r": "5", "fill": "#3867a5", "stroke": "#ffffff", "stroke-width": "1.5"})
        _element(circle, "title", text=f"{label}: x={_fmt(x_value)} {x_unit}; y={_fmt(y_value)} {y_unit}")

    raw = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return asset(
        "synthetic-point-scatter", "image/svg+xml", raw,
        chart_kind="scatter", declared_data_origin="synthetic", origin_verified=False,
        estimand=estimand, x_axis={"label": axes["x_axis"][0], "unit": x_unit},
        y_axis={"label": axes["y_axis"][0], "unit": y_unit},
        point_count=len(points), source_values=[{"x": x, "y": y, "label": label} for x, y, label in points],
        limitations=["Point display only; no fit, interpolation, probability plot, confidence interval, or forecast.",
                     "Synthetic origin is caller-declared and is not independently verified."],
    )

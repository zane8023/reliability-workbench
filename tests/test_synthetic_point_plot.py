import base64
from contextlib import ExitStack
from copy import deepcopy
from decimal import Decimal, Inexact, localcontext
from fractions import Fraction
import hashlib
import json
import math
import random
import struct
import sys
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from app.services.synthetic_point_plot import MAX_POINTS, SVG_NS, render_synthetic_result_scatter
from app.services.saved_report import MAX_BYTES
from app.services import saved_report, synthetic_point_plot


def payload(points=None):
    return {
        "data_origin": "synthetic",
        "title": "Synthetic reliability points",
        "estimand": "Reliability R(t)",
        "x_axis": {"label": "Time", "unit": "hour"},
        "y_axis": {"label": "Reliability", "unit": "probability"},
        "points": points if points is not None else [
            {"x": 0.0, "y": 1.0, "label": "start"},
            {"x": 100.0, "y": 0.99, "label": "synthetic point"},
        ],
    }


class SyntheticPointPlotTests(unittest.TestCase):
    def test_svg_scatter_has_declared_units_and_no_fit_claim(self):
        asset = render_synthetic_result_scatter(payload())
        self.assertEqual(asset["mime_type"], "image/svg+xml")
        self.assertEqual(asset["chart_kind"], "scatter")
        self.assertFalse(asset["origin_verified"])
        raw = base64.b64decode(asset["content_base64"], validate=True)
        self.assertEqual(len(raw), asset["byte_size"])
        self.assertEqual(__import__("hashlib").sha256(raw).hexdigest(), asset["sha256"])
        root = ET.fromstring(raw)
        circles = root.findall(f"{{{SVG_NS}}}circle")
        self.assertEqual(len(circles), 2)
        self.assertIn("Time (hour)", "".join(root.itertext()))
        self.assertIn("Reliability (probability)", "".join(root.itertext()))
        self.assertIn("no fitted curve", "".join(root.itertext()))
        for circle in circles:
            self.assertTrue(math.isfinite(float(circle.attrib["cx"])))
            self.assertTrue(math.isfinite(float(circle.attrib["cy"])))

    def test_malicious_text_is_xml_text_not_active_markup(self):
        data = payload([{ "x": 1, "y": 2, "label": "<script>alert(1)</script>" }])
        data["title"] = "<img src=x onerror=alert(1)>"
        raw = base64.b64decode(render_synthetic_result_scatter(data)["content_base64"])
        text = raw.decode("utf-8")
        self.assertIn("&lt;script&gt;", text)
        self.assertIn("&lt;img", text)
        self.assertNotIn("<script", text)
        self.assertNotIn("<img", text)
        ET.fromstring(raw)

    def test_extreme_and_constant_axes_keep_coordinates_finite(self):
        data = payload([
            {"x": -1e308, "y": 5.0}, {"x": 1e308, "y": 5.0},
        ])
        root = ET.fromstring(base64.b64decode(render_synthetic_result_scatter(data)["content_base64"]))
        circles = root.findall(f"{{{SVG_NS}}}circle")
        self.assertEqual(len(circles), 2)
        self.assertTrue(all(math.isfinite(float(c.attrib["cx"])) for c in circles))
        self.assertTrue(all(math.isfinite(float(c.attrib["cy"])) for c in circles))
        self.assertEqual(circles[0].attrib["cy"], circles[1].attrib["cy"])

    def test_repeatability_and_strict_synthetic_contract(self):
        self.assertEqual(render_synthetic_result_scatter(payload()), render_synthetic_result_scatter(payload()))
        bad = payload(); bad["data_origin"] = "observed"
        with self.assertRaisesRegex(ValueError, "synthetic_data_required"):
            render_synthetic_result_scatter(bad)
        bad = payload(); bad["data_origin"] = object()
        with self.assertRaisesRegex(ValueError, "synthetic_data_required"):
            render_synthetic_result_scatter(bad)
        with self.assertRaisesRegex(ValueError, "request_fields_invalid"):
            render_synthetic_result_scatter({**payload(), "secret": "not accepted"})

    def test_rejects_bool_nonfinite_bad_units_and_excess_points(self):
        for value in (True, float("nan"), float("inf"), "1.0", 10**1000):
            data = payload([{ "x": value, "y": 0 }])
            with self.assertRaises(ValueError):
                render_synthetic_result_scatter(data)
        data = payload(); data["x_axis"]["unit"] = "\x00"
        with self.assertRaisesRegex(ValueError, "x_axis_unit_invalid"):
            render_synthetic_result_scatter(data)
        data = payload([{ "x": i, "y": i } for i in range(MAX_POINTS + 1)])
        with self.assertRaisesRegex(ValueError, "point_count_invalid"):
            render_synthetic_result_scatter(data)

    def test_maximum_accepted_payload_stays_under_asset_limit(self):
        data = payload([
            {"x": (-1.0 if index % 2 else 1.0) * 1.7976931348623157e308,
             "y": index / MAX_POINTS, "label": "L" * 80}
            for index in range(MAX_POINTS)
        ])
        data["title"] = "T" * 120
        data["estimand"] = "E" * 100
        data["x_axis"] = {"label": "X" * 80, "unit": "U" * 40}
        data["y_axis"] = {"label": "Y" * 80, "unit": "V" * 40}
        result = render_synthetic_result_scatter(data)
        self.assertLessEqual(result["byte_size"], MAX_BYTES)


class SyntheticPointPlotRegressionTests(unittest.TestCase):
    """Observable SVG, asset and input contracts for the synthetic renderer."""

    def assert_scatter_alignment(self, points):
        result = render_synthetic_result_scatter(payload(points))
        raw = base64.b64decode(result["content_base64"], validate=True)
        root = ET.fromstring(raw)
        circles = root.findall(f"{{{SVG_NS}}}circle")
        self.assertEqual(len(circles), len(points))
        lines = root.findall(f"{{{SVG_NS}}}line")
        xs = sorted({float(line.attrib[key]) for line in lines for key in ("x1", "x2")})
        ys = sorted({float(line.attrib[key]) for line in lines for key in ("y1", "y2")})
        left, right, top, bottom = xs[0], xs[-1], ys[0], ys[-1]
        self.assertLess(left, right)
        self.assertLess(top, bottom)
        texts = root.findall(f"{{{SVG_NS}}}text")
        x_ticks = sorted(
            (node for node in texts if node.attrib.get("font-size") == "10"
             and node.attrib.get("text-anchor") == "middle"),
            key=lambda node: float(node.attrib["x"]),
        )
        y_ticks = sorted(
            (node for node in texts if node.attrib.get("text-anchor") == "end"),
            key=lambda node: -float(node.attrib["y"]),
        )
        self.assertEqual(len(x_ticks), len(xs))
        self.assertEqual(len(y_ticks), len(ys))
        self.assertGreaterEqual(len(x_ticks), 3)
        self.assertGreaterEqual(len(y_ticks), 3)
        for tick, grid_x in zip(x_ticks, xs):
            self.assertAlmostEqual(float(tick.attrib["x"]), grid_x)
        for tick, grid_y in zip(y_ticks, reversed(ys)):
            baseline_offset = float(tick.attrib["y"]) - grid_y
            self.assertGreaterEqual(baseline_offset, 0)
            self.assertLessEqual(baseline_offset, float(tick.attrib["font-size"]))
        for axis, ticks in (("x", x_ticks), ("y", y_ticks)):
            values = [float(point[axis]) for point in points]
            low, high = min(values), max(values)
            # Exact rational expectations avoid reproducing the renderer's
            # binary64 subtraction, overflow or cancellation. Decimal parses
            # five-significant-figure labels without overflowing near DBL_MAX.
            with localcontext() as context:
                context.prec = 80
                lo, hi = Fraction(low), Fraction(high)
                half_subnormal = Decimal.from_float(math.ulp(0.0)) / 2
                for index, tick in enumerate(ticks):
                    exact = lo + (hi - lo) * Fraction(index, len(ticks) - 1)
                    expected = Decimal(exact.numerator) / Decimal(exact.denominator)
                    actual = Decimal(tick.text)
                    self.assertTrue(actual.is_finite())
                    tolerance = max(abs(expected) * Decimal("0.00005"), half_subnormal)
                    self.assertLessEqual(abs(actual - expected), tolerance,
                                         f"{axis} tick {index}: {actual} does not label {expected}")
            for point, circle in zip(points, circles):
                ratio = (0.5 if low == high else float(
                    (Fraction(float(point[axis])) - Fraction(low)) /
                    (Fraction(high) - Fraction(low))))
                coordinate = float(circle.attrib["c" + axis])
                expected = (left + (right - left) * ratio if axis == "x"
                            else bottom - (bottom - top) * ratio)
                self.assertTrue(math.isfinite(coordinate))
                self.assertGreaterEqual(coordinate, left if axis == "x" else top)
                self.assertLessEqual(coordinate, right if axis == "x" else bottom)
                self.assertAlmostEqual(coordinate, expected, places=5)
        return root, result

    def test_y_tick_labels_align_with_asymmetric_min_midpoint_and_max_points(self):
        self.assert_scatter_alignment([
            {"x": 8, "y": 10}, {"x": -6, "y": 3},
            {"x": -8, "y": 2}, {"x": 0, "y": 6},
        ])

    def test_asymmetric_magnitude_endpoint_ticks_preserve_supplied_bounds(self):
        # low + (high - low) can lose the small endpoint to cancellation.
        for values in ([-1e20, 0.0, 1.0], [-1.0, 0.0, 1e20]):
            with self.subTest(bounds=(values[0], values[-1])):
                self.assert_scatter_alignment([
                    {"x": x, "y": y} for x, y in zip(values, reversed(values))
                ])

    def test_extreme_subnormal_and_adjacent_varying_axes(self):
        largest, tiny = sys.float_info.max, math.ulp(0.0)
        cases = {
            "opposite_extremes": [-largest, 0.0, largest],
            "positive_extremes": [largest / 2, largest * 0.75, largest],
            "negative_extremes": [-largest, -largest * 0.75, -largest / 2],
            "subnormals": [-4 * tiny, 0.0, 4 * tiny],
            "smallest_positive_span": [0.0, tiny],
            "adjacent_large_values": [math.nextafter(largest, 0.0), largest],
            "adjacent_normal_values": [1.0, math.nextafter(1.0, math.inf)],
        }
        for name, values in cases.items():
            with self.subTest(case=name):
                self.assert_scatter_alignment([
                    {"x": x, "y": y} for x, y in zip(values, reversed(values))
                ])

    def test_constant_axes_and_singleton_are_centered_and_correctly_labeled(self):
        for value in (0.0, -0.0, 5.0, -sys.float_info.max, sys.float_info.max, math.ulp(0.0)):
            for constant_axis in ("x", "y", "both"):
                with self.subTest(value=value, constant_axis=constant_axis):
                    self.assert_scatter_alignment([
                        {"x": value if constant_axis in ("x", "both") else variable,
                         "y": value if constant_axis in ("y", "both") else variable}
                        for variable in (-3.0, 0.0, 9.0)
                    ])
        self.assert_scatter_alignment([{"x": 7.0, "y": -2.0}])

    def test_missing_unknown_and_wrongly_shaped_fields_are_rejected(self):
        for field in payload():
            data = payload()
            del data[field]
            with self.subTest(missing=field), self.assertRaisesRegex(ValueError, "^request_fields_invalid$"):
                render_synthetic_result_scatter(data)
        for data in (None, [], "synthetic", {**payload(), "output_path": "must-not-write.svg"}):
            with self.subTest(request_type=type(data).__name__), self.assertRaisesRegex(ValueError, "^request_fields_invalid$"):
                render_synthetic_result_scatter(data)
        for axis in ("x_axis", "y_axis"):
            for value in (None, [], {"label": "x"}, {"unit": "h"},
                          {"label": "x", "unit": "h", "secret": "PRIVATE_SENTINEL"}):
                data = payload()
                data[axis] = value
                with self.subTest(axis=axis, value=value), self.assertRaisesRegex(ValueError, f"^{axis}_fields_invalid$"):
                    render_synthetic_result_scatter(data)
        for point in (None, [], {"x": 1}, {"y": 2},
                      {"x": 1, "y": 2, "secret": "PRIVATE_SENTINEL"}):
            with self.subTest(point=point), self.assertRaisesRegex(ValueError, "^point_fields_invalid$"):
                render_synthetic_result_scatter(payload([point]))
        for origin in (None, True, "Synthetic", " synthetic ", "observed"):
            with self.subTest(origin=origin), self.assertRaisesRegex(ValueError, "^synthetic_data_required$"):
                render_synthetic_result_scatter({**payload(), "data_origin": origin})

    def test_empty_nonlist_and_overlimit_point_collections_are_rejected(self):
        for points in (None, [], (), ({"x": 1, "y": 2},), {}, "points", 1,
                       [{"x": 1, "y": 2}] * (MAX_POINTS + 1)):
            data = payload()
            data["points"] = points
            with self.subTest(collection_type=type(points).__name__), self.assertRaisesRegex(ValueError, "^point_count_invalid$"):
                render_synthetic_result_scatter(data)

    def test_invalid_numeric_types_and_nonfinite_values_on_both_axes(self):
        class IntegerSubclass(int):
            pass

        invalid = (True, False, None, "1.0", Decimal("1"), 1 + 0j, IntegerSubclass(1),
                   float("nan"), float("inf"), -float("inf"), 10**1000, [])
        for axis in ("x", "y"):
            for value in invalid:
                point = {"x": 0, "y": 0}
                point[axis] = value
                with self.subTest(axis=axis, value_type=type(value).__name__), self.assertRaisesRegex(ValueError, f"^{axis}_invalid$"):
                    render_synthetic_result_scatter(payload([point]))

    def test_text_type_length_and_xml_character_limits_for_every_text_field(self):
        fields = (
            (("title",), 120, "title"), (("estimand",), 100, "estimand"),
            (("x_axis", "label"), 80, "x_axis_label"),
            (("x_axis", "unit"), 40, "x_axis_unit"),
            (("y_axis", "label"), 80, "y_axis_label"),
            (("y_axis", "unit"), 40, "y_axis_unit"),
            (("points", 0, "label"), 80, "point_label"),
        )
        for path, maximum, error in fields:
            for value in (None, True, 1, "", " \t\n", "x" * (maximum + 1),
                          "before\x00after", "before\x0bafter", "before\ud800after", "before\ufffeafter"):
                data = payload()
                target = data
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.subTest(field=error, value=repr(value)), self.assertRaisesRegex(ValueError, f"^{error}_invalid$"):
                    render_synthetic_result_scatter(data)

    def test_all_caller_text_is_passive_xml_and_unicode_survives(self):
        text = '<svg onload="x">&\' 中文 📉'
        data = payload([{"x": 1, "y": 2, "label": text}])
        data["title"] = data["estimand"] = text
        data["x_axis"] = data["y_axis"] = {"label": text, "unit": text}
        result = render_synthetic_result_scatter(data)
        raw = base64.b64decode(result["content_base64"], validate=True)
        root = ET.fromstring(raw)
        allowed = {"svg", "title", "desc", "rect", "text", "line", "circle"}
        for node in root.iter():
            self.assertTrue(node.tag.startswith(f"{{{SVG_NS}}}"))
            self.assertIn(node.tag.rsplit("}", 1)[-1], allowed)
            for key, value in node.attrib.items():
                local_name = key.rsplit("}", 1)[-1].lower()
                self.assertFalse(local_name.startswith("on"))
                self.assertNotIn(local_name, ("href", "src"))
                self.assertNotIn("url(", value.lower())
        self.assertNotIn(b"<!DOCTYPE", raw)
        self.assertNotIn(b"<!ENTITY", raw)
        self.assertEqual(root.find(f"{{{SVG_NS}}}title").text, text)
        self.assertIn(f"{text} ({text})", [node.text for node in root.findall(f"{{{SVG_NS}}}text")])
        self.assertEqual(root.find(f"{{{SVG_NS}}}circle/{{{SVG_NS}}}title").text,
                         f"{text}: x=1 {text}; y=2 {text}")
        self.assertEqual(result["source_values"][0]["label"], text)

    def test_metadata_order_float_conversion_units_and_origin_disclaimer(self):
        data = payload([{"x": 2**53 + 1, "y": -0.0},
                        {"x": -3, "y": 0.25, "label": "  measured-looking label  "}])
        data["title"] = "  Display title  "
        data["estimand"] = "  Declared result  "
        data["x_axis"] = {"label": "  Time  ", "unit": "  h  "}
        data["y_axis"] = {"label": "  Value  ", "unit": "  unit  "}
        result = render_synthetic_result_scatter(data)
        self.assertEqual(result["source_values"], [
            {"x": float(2**53 + 1), "y": -0.0, "label": "Point 1"},
            {"x": -3.0, "y": 0.25, "label": "measured-looking label"},
        ])
        self.assertEqual(math.copysign(1.0, result["source_values"][0]["y"]), -1.0)
        self.assertEqual(result["point_count"], 2)
        self.assertEqual(result["estimand"], "Declared result")
        self.assertEqual(result["x_axis"], {"label": "Time", "unit": "h"})
        self.assertEqual(result["y_axis"], {"label": "Value", "unit": "unit"})
        self.assertEqual(result["declared_data_origin"], "synthetic")
        self.assertIs(result["origin_verified"], False)
        self.assertIn("not independently verified", " ".join(result["limitations"]))
        self.assertIn("no fit", " ".join(result["limitations"]))
        self.assertEqual(json.loads(json.dumps(result, allow_nan=False)), result)
        root = ET.fromstring(base64.b64decode(result["content_base64"], validate=True))
        self.assertEqual(root.find(f"{{{SVG_NS}}}title").text, "Display title")
        by_id = {node.attrib["id"]: node for node in root.iter() if "id" in node.attrib}
        self.assertEqual(root.attrib["role"], "img")
        for reference in root.attrib["aria-labelledby"].split():
            self.assertIn(reference, by_id)
            self.assertTrue(by_id[reference].text)
        descriptions = " ".join(node.text or "" for node in root.findall(f"{{{SVG_NS}}}desc"))
        self.assertIn("not independently verified", descriptions)
        self.assertIn("no fitted curve", descriptions)

    def test_current_saved_report_asset_envelope_and_size_guard_are_used(self):
        with mock.patch.object(synthetic_point_plot, "asset", wraps=saved_report.asset) as wrapper:
            result = render_synthetic_result_scatter(payload())
        wrapper.assert_called_once()
        raw = base64.b64decode(result["content_base64"], validate=True)
        expected = saved_report.asset("synthetic-point-scatter", "image/svg+xml", raw)
        for key, value in expected.items():
            self.assertEqual(result[key], value)
        self.assertEqual(result["asset_ref"], "synthetic-point-scatter-" + hashlib.sha256(raw).hexdigest()[:24])
        with mock.patch.object(saved_report, "MAX_BYTES", len(raw) - 1):
            with self.assertRaisesRegex(ValueError, "^REPORT_ASSET_SIZE_EXCEEDED$"):
                render_synthetic_result_scatter(payload())

    def test_input_is_not_mutated_and_output_containers_are_independent(self):
        data = payload()
        before = deepcopy(data)
        first = render_synthetic_result_scatter(data)
        expected = deepcopy(first)
        self.assertEqual(data, before)
        first["source_values"][0]["label"] = "changed output"
        first["source_values"].append({"x": 9, "y": 9, "label": "extra"})
        first["x_axis"]["unit"] = "changed unit"
        first["limitations"].clear()
        self.assertEqual(data, before)
        self.assertEqual(render_synthetic_result_scatter(data), expected)
        bad = payload()
        bad["points"][1]["y"] = "not numeric"
        before_bad = deepcopy(bad)
        with self.assertRaises(ValueError):
            render_synthetic_result_scatter(bad)
        self.assertEqual(bad, before_bad)

    def test_renderer_does_not_open_files_network_database_or_processes(self):
        # Common external I/O entry points are guarded during valid and invalid
        # rendering. This focused check is not a claim of a general sandbox.
        targets = ("builtins.open", "io.open", "os.open", "socket.socket",
                   "socket.create_connection", "sqlite3.connect", "subprocess.Popen")
        with ExitStack() as stack:
            guards = [stack.enter_context(mock.patch(target, side_effect=AssertionError(target)))
                      for target in targets]
            result = render_synthetic_result_scatter(payload())
            with self.assertRaisesRegex(ValueError, "^synthetic_data_required$"):
                render_synthetic_result_scatter({**payload(), "data_origin": "observed"})
        self.assertEqual(result["point_count"], 2)
        for guard in guards:
            guard.assert_not_called()

    def test_maximum_escaped_and_multibyte_labels_fit_asset_limit(self):
        for character in ("&", "📉"):
            data = payload([{"x": -sys.float_info.max if index % 2 else sys.float_info.max,
                             "y": math.ulp(0.0) * index, "label": character * 80}
                            for index in range(MAX_POINTS)])
            data["title"] = character * 120
            data["estimand"] = character * 100
            data["x_axis"] = {"label": character * 80, "unit": character * 40}
            data["y_axis"] = {"label": character * 80, "unit": character * 40}
            with self.subTest(character=character):
                result = render_synthetic_result_scatter(data)
                raw = base64.b64decode(result["content_base64"], validate=True)
                self.assertEqual(len(raw), result["byte_size"])
                self.assertLessEqual(len(raw), MAX_BYTES)
                root = ET.fromstring(raw)
                self.assertEqual(len(root.findall(f"{{{SVG_NS}}}circle")), MAX_POINTS)
                self.assertEqual(result["point_count"], MAX_POINTS)

    def assert_exact_quarter_tick_labels(self, low, high, expected_residual=None):
        """Check the public SVG against an independent exact-decimal oracle."""
        result = render_synthetic_result_scatter(payload([
            {"x": low, "y": high}, {"x": high, "y": low},
        ]))
        root = ET.fromstring(base64.b64decode(result["content_base64"], validate=True))
        texts = root.findall(f"{{{SVG_NS}}}text")
        x_ticks = sorted(
            (node for node in texts if node.attrib.get("font-size") == "10"
             and node.attrib.get("text-anchor") == "middle"),
            key=lambda node: float(node.attrib["x"]),
        )
        y_ticks = sorted(
            (node for node in texts if node.attrib.get("text-anchor") == "end"),
            key=lambda node: -float(node.attrib["y"]),
        )
        with localcontext() as context:
            # 1600 digits covers the entire binary64 exponent range, even a
            # DBL_MAX/subnormal pair. Trap any accidental oracle rounding.
            context.prec = 1600
            context.traps[Inexact] = True
            lo, hi = Decimal.from_float(low), Decimal.from_float(high)
            expected = []
            for index in range(5):
                exact = (lo * (4 - index) + hi * index) / 4
                rounded = float(exact)
                self.assertTrue(math.isfinite(rounded))
                self.assertLessEqual(low, rounded)
                self.assertLessEqual(rounded, high)
                expected.append("0" if rounded == 0 else format(rounded, ".5g"))
        if expected_residual is not None:
            index, label = expected_residual
            self.assertEqual(expected[index], label)
        for axis, ticks in (("x", x_ticks), ("y", y_ticks)):
            self.assertEqual(len(ticks), 5)
            for index, (tick, label) in enumerate(zip(ticks, expected)):
                with self.subTest(axis=axis, tick=index):
                    self.assertEqual(tick.text, label)
                    self.assertTrue(Decimal(tick.text).is_finite())
        circles = root.findall(f"{{{SVG_NS}}}circle")
        self.assertEqual([(circle.attrib["cx"], circle.attrib["cy"]) for circle in circles],
                         [("92.000000", "94.000000"), ("690.000000", "374.000000")])
        self.assertEqual(result["source_values"], [
            {"x": low, "y": high, "label": "Point 1"},
            {"x": high, "y": low, "label": "Point 2"},
        ])

    def test_mirrored_midpoint_residuals_label_both_axes_exactly(self):
        larger = math.nextafter(1e20, math.inf)
        for low, high, label in ((-1e20, larger, "8192"), (-larger, 1e20, "-8192")):
            with self.subTest(low=low, high=high):
                self.assert_exact_quarter_tick_labels(low, high, (2, label))

    def test_quarter_cancellation_residuals_label_both_axes_exactly(self):
        smaller = math.nextafter(1e20, 0.0)
        larger = math.nextafter(1e20, math.inf)
        cases = ((-larger, 3e20, 1, "-12288"), (-smaller, 3e20, 1, "12288"),
                 (-3e20, larger, 3, "12288"), (-3e20, smaller, 3, "-12288"))
        for low, high, index, label in cases:
            with self.subTest(low=low, high=high, residual_tick=index):
                self.assert_exact_quarter_tick_labels(low, high, (index, label))

    def test_subnormal_quarter_ticks_round_once_to_nearest_even(self):
        tiny = math.ulp(0.0)
        # Include both sides of half-ulp ties, ties to even at one and two
        # subnormal ulps, zero crossings and the normal/subnormal boundary.
        cases = ((tiny, 2 * tiny), (-2 * tiny, -tiny), (0.0, tiny), (-tiny, 0.0),
                 (tiny, 3 * tiny), (-3 * tiny, -tiny), (-tiny, 2 * tiny),
                 (-2 * tiny, tiny),
                 (math.nextafter(sys.float_info.min, 0.0), sys.float_info.min))
        for low, high in cases:
            with self.subTest(low=low.hex(), high=high.hex()):
                self.assert_exact_quarter_tick_labels(low, high)

    def test_extreme_quarter_ticks_stay_finite_and_preserve_bounds(self):
        largest, tiny = sys.float_info.max, math.ulp(0.0)
        adjacent = math.nextafter(largest, 0.0)
        cases = ((-largest, largest), (-largest, adjacent), (-adjacent, largest),
                 (largest / 2, largest), (-largest, -largest / 2),
                 (adjacent, largest), (-largest, -adjacent),
                 (tiny, largest), (-largest, -tiny), (-tiny, largest),
                 (-largest, tiny), (1.0, math.nextafter(1.0, math.inf)))
        for low, high in cases:
            with self.subTest(low=low.hex(), high=high.hex()):
                self.assert_exact_quarter_tick_labels(low, high)

    def test_seeded_binary64_quarter_ticks_match_exact_decimal_labels(self):
        generator = random.Random(20261108)
        for case in range(160):
            values = []
            while len(values) < 2:
                value = struct.unpack(">d", generator.getrandbits(64).to_bytes(8, "big"))[0]
                if math.isfinite(value) and value not in values:
                    values.append(value)
            low, high = sorted(values)
            with self.subTest(case=case, low=low.hex(), high=high.hex()):
                self.assert_exact_quarter_tick_labels(low, high)


if __name__ == "__main__":
    unittest.main()

"""Experimental in-memory CSV adapter; no file, network or database access."""
import csv
from decimal import Decimal, InvalidOperation
import io
import math
import re

MAX_BYTES = 65536
MAX_ROWS = 5000
MAX_CELL = 64
UNITS = ("second", "minute", "hour", "day", "year")
NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


def _error(code, line=None):
    error = {"code": code}
    if line is not None:
        error["line"] = line
    return {"ok": False, "error": error}


def parse_observations(raw, time_unit):
    """Parse synthetic CSV bytes into a narrow exponential-fit request.

    Only trusted single-user in-process callers are in scope. Decimal inputs
    become binary floats, so a successful conversion does not imply exactness.
    """
    try:
        return _parse(raw, time_unit)
    except MemoryError:
        raise
    except Exception:
        return _error("INTERNAL_ERROR")


def _parse(raw, time_unit):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        return _error("INVALID_INPUT_SIZE_OR_TYPE")
    if type(time_unit) is not str or time_unit not in UNITS:
        return _error("INVALID_TIME_UNIT")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError:
        return _error("INVALID_ENCODING")
    if "\x00" in text:
        return _error("INVALID_TEXT")
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        try:
            header = next(reader)
        except StopIteration:
            return _error("EMPTY_INPUT")
        if len(header) != len(set(header)):
            return _error("DUPLICATE_HEADER", reader.line_num)
        if header != ["kind", "time"]:
            return _error("INVALID_HEADER", reader.line_num)
        observations = []
        for row in reader:
            line = reader.line_num
            if len(row) != 2:
                return _error("INVALID_ROW_WIDTH", line)
            if len(observations) >= MAX_ROWS:
                return _error("ROW_LIMIT_EXCEEDED", line)
            if any(len(cell) > MAX_CELL for cell in row):
                return _error("CELL_LIMIT_EXCEEDED", line)
            kind, time_text = row
            if kind not in ("exact", "right_censored"):
                return _error("INVALID_EVENT_KIND", line)
            if not NUMBER.fullmatch(time_text):
                return _error("INVALID_TIME", line)
            try:
                value = Decimal(time_text)
                if not value.is_finite() or value <= 0 or value > Decimal(2**53):
                    return _error("INVALID_TIME", line)
                time_value = float(value)
            except (InvalidOperation, OverflowError, ValueError):
                return _error("INVALID_TIME", line)
            if not math.isfinite(time_value) or time_value <= 0:
                return _error("INVALID_TIME", line)
            observations.append({"kind": kind, "time": time_value})
    except csv.Error:
        return _error("INVALID_CSV", reader.line_num)
    if not observations:
        return _error("NO_OBSERVATIONS")
    return {"ok": True, "request": {"time_unit": time_unit, "observations": observations},
            "limitations": ["Decimal time values are converted to binary floats and may be rounded.",
                            "Parsing does not validate censoring assumptions or engineering applicability.",
                            "No file, network, database, or multi-user service is provided."]}

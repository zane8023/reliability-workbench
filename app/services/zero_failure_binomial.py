"""Zero observed events: one-sided exact binomial upper bound, local trial.

Formula: solve (1-p)**n = 1-confidence for p; this is not a rate.
The implementation is newly written and does not copy the internal service.
"""
import math
import sys
import unicodedata


def zero_failure_upper(sample_size, confidence_level, *, event_definition, observation_window):
    if type(sample_size) is not int or not 1 <= sample_size <= 10_000_000:
        raise ValueError("sample_size must be an integer from 1 to 10000000")
    if type(confidence_level) not in (int, float):
        raise ValueError("confidence_level must be a finite number in (0,1)")
    try: confidence=float(confidence_level)
    except OverflowError as exc: raise ValueError("confidence_level outside float range") from exc
    if not math.isfinite(confidence) or not 0.0 < confidence < 1.0:
        raise ValueError("confidence_level must be a finite number in (0,1)")
    def label(value,name):
        if type(value) is not str or len(value)>500 or not any(not c.isspace() and not unicodedata.category(c).startswith("C") for c in value):
            raise ValueError(name+" must be a meaningful string of at most 500 characters")
        try: value.encode("utf-8")
        except UnicodeEncodeError as exc: raise ValueError(name+" must be valid UTF-8 text") from exc
        return value.strip()
    event=label(event_definition,"event_definition");window=label(observation_window,"observation_window")
    upper=-math.expm1(math.log1p(-confidence)/sample_size)
    if not math.isfinite(upper) or not sys.float_info.min <= upper <= 1.0:
        raise ValueError("upper bound is not representable as a positive normal float")
    return {"method":"exact_one_sided_binomial", "failure_count":0, "sample_size":sample_size,
            "confidence_level":confidence, "failure_probability_upper":upper,
            "event_definition":event, "observation_window":window,
            "validation_status":"experimental_synthetic_checks_only",
            "assumptions":["Independent units with a common event probability and the same defined observation window.",
                           "All tested units have a known binary outcome and zero observed events."],
            "limitations":["Probability for the stated test and window only; not a time rate, field forecast, or guarantee."]}

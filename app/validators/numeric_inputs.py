"""Numeric inputs retain normal float coercion but never accept booleans."""
from typing import Annotated
from pydantic import BeforeValidator


def _reject_boolean(value):
    if isinstance(value, bool):
        raise ValueError("boolean values are not valid numeric inputs")
    return value


NonBooleanFloat = Annotated[float, BeforeValidator(_reject_boolean)]

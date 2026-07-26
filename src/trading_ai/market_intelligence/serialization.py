from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import numpy as np


def python_scalar(value: Any) -> Any:
    """Convert scalar values produced by NumPy/Pandas to DB-driver-safe Python types."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Decimal):
        return float(value)
    return value


def to_python(value: Any) -> Any:
    """Recursively normalize analytics payloads to native, JSON-safe Python values."""
    value = python_scalar(value)

    if isinstance(value, np.ndarray):
        return [to_python(item) for item in value.tolist()]
    if isinstance(value, Mapping):
        return {str(key): to_python(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_python(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def json_payload(value: Any, *, indent: int | None = None) -> str:
    """Serialize a payload after recursively removing NumPy/Pandas-specific values."""
    return json.dumps(to_python(value), indent=indent, allow_nan=False)

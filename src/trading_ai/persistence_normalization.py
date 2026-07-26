"""Canonical conversion of analytics values before SQL/JSON persistence.

NumPy and pandas values are intentionally converted at the persistence boundary so
psycopg2 never receives representations such as ``np.float64(63.56)`` and JSON
never contains NaN/Infinity or implementation-specific scalar strings.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
import math
from pathlib import Path
from typing import Any, Mapping


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        import pandas as pd  # type: ignore
        missing = pd.isna(value)
        if isinstance(missing, bool):
            return missing
    except (ImportError, TypeError, ValueError):
        pass
    return False


def to_native(value: Any) -> Any:
    """Recursively convert scientific Python values to DB/JSON-safe primitives."""
    if _is_missing(value):
        return None
    if is_dataclass(value):
        return to_native(asdict(value))
    if isinstance(value, Mapping):
        return {str(to_native(k)): to_native(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_native(v) for v in value]
    module = type(value).__module__
    if module.startswith("pandas"):
        to_pydatetime = getattr(value, "to_pydatetime", None)
        if callable(to_pydatetime):
            return to_native(to_pydatetime())
    if isinstance(value, (str, bytes, bool, int, datetime, date, Decimal, Path)):
        return str(value) if isinstance(value, Path) else value
    if isinstance(value, float):
        converted = float(value)
        return converted if math.isfinite(converted) else None

    module = type(value).__module__
    name = type(value).__name__
    if module.startswith("numpy"):
        if name.startswith("bool"):
            return bool(value)
        if name.startswith(("int", "uint")):
            return int(value)
        if name.startswith(("float", "half")):
            converted = float(value)
            return converted if math.isfinite(converted) else None
        if name.startswith("datetime64"):
            try:
                return to_native(value.astype("datetime64[us]").item())
            except (ValueError, TypeError, OverflowError):
                return str(value)

    # NumPy scalar/array support without making NumPy a hard dependency.
    item = getattr(value, "item", None)
    if callable(item):
        try:
            converted = item()
            if converted is not value:
                return to_native(converted)
        except (ValueError, TypeError):
            pass
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        try:
            return to_native(tolist())
        except (ValueError, TypeError):
            pass

    # pandas.Timestamp and similar objects.
    to_pydatetime = getattr(value, "to_pydatetime", None)
    if callable(to_pydatetime):
        return to_native(to_pydatetime())
    return value


def native_params(params: Mapping[str, Any]) -> dict[str, Any]:
    result = to_native(params)
    if not isinstance(result, dict):
        raise TypeError("SQL parameters must normalize to a dictionary")
    return result


def json_ready(value: Any) -> Any:
    value = to_native(value)
    if isinstance(value, Mapping):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, (datetime, date, Decimal)):
        return value.isoformat() if hasattr(value, "isoformat") else str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def strict_json_dumps(value: Any, **kwargs: Any) -> str:
    import json
    return json.dumps(json_ready(value), allow_nan=False, **kwargs)

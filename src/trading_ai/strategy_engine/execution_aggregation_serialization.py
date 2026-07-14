from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any


def execution_aggregation_to_dict(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return execution_aggregation_to_dict(asdict(value))
    if isinstance(value, dict):
        return {str(k): execution_aggregation_to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [execution_aggregation_to_dict(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return str(value)

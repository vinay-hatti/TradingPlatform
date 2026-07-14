from dataclasses import asdict, is_dataclass
from enum import Enum
from datetime import date, datetime
from typing import Any


def execution_analytics_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return execution_analytics_to_dict(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): execution_analytics_to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [execution_analytics_to_dict(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value

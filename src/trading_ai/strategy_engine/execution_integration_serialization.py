from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any


def execution_integration_to_dict(value: Any):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {k: execution_integration_to_dict(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): execution_integration_to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [execution_integration_to_dict(v) for v in value]
    if hasattr(value, "item"):
        try: return value.item()
        except Exception: pass
    if hasattr(value, "__dict__"):
        return {k: execution_integration_to_dict(v) for k, v in vars(value).items() if not k.startswith("_")}
    return str(value)

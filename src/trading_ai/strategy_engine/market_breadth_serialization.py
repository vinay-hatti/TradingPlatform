from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any


def market_breadth_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return market_breadth_to_dict(asdict(value))
    if isinstance(value, dict):
        return {str(k): market_breadth_to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [market_breadth_to_dict(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value

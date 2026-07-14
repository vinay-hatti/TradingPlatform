from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any


def portfolio_optimization_frontier_to_dict(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            key: portfolio_optimization_frontier_to_dict(item)
            for key, item in asdict(value).items()
        }
    if isinstance(value, dict):
        return {
            str(key): portfolio_optimization_frontier_to_dict(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [portfolio_optimization_frontier_to_dict(item) for item in value]
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return portfolio_optimization_frontier_to_dict(value.to_dict())
    if hasattr(value, "__dict__"):
        return {
            key: portfolio_optimization_frontier_to_dict(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return str(value)

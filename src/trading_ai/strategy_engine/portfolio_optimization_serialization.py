from dataclasses import asdict, is_dataclass
from enum import Enum


def portfolio_optimization_to_dict(value):
    if value is None:
        return None
    if is_dataclass(value):
        return {key: portfolio_optimization_to_dict(item) for key, item in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): portfolio_optimization_to_dict(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [portfolio_optimization_to_dict(item) for item in value]
    return value

from dataclasses import asdict, is_dataclass
from enum import Enum


def walk_forward_integration_to_dict(value):
    if is_dataclass(value):
        return walk_forward_integration_to_dict(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): walk_forward_integration_to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [walk_forward_integration_to_dict(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value

from dataclasses import asdict, is_dataclass
from enum import Enum


def walk_forward_governance_to_dict(value):
    if is_dataclass(value):
        return {k: walk_forward_governance_to_dict(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): walk_forward_governance_to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [walk_forward_governance_to_dict(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value

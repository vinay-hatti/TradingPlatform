from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

import numpy as np


def walk_forward_adapter_to_dict(value: Any) -> Any:
    """Serialize adapter diagnostics and normalized evaluation profiles."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            key: walk_forward_adapter_to_dict(item)
            for key, item in asdict(value).items()
        }
    if isinstance(value, dict):
        return {
            str(key): walk_forward_adapter_to_dict(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [walk_forward_adapter_to_dict(item) for item in value]
    if hasattr(value, "__dict__"):
        return {
            key: walk_forward_adapter_to_dict(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return str(value)

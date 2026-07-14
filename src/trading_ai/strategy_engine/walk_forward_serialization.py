from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

import numpy as np


def walk_forward_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return walk_forward_to_dict(asdict(value))
    if isinstance(value, dict):
        return {str(k): walk_forward_to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [walk_forward_to_dict(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.generic):
        return value.item()
    return value

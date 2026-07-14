from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

import numpy as np


def walk_forward_probability_calibration_to_dict(value: Any):
    if is_dataclass(value):
        return {key: walk_forward_probability_calibration_to_dict(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): walk_forward_probability_calibration_to_dict(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [walk_forward_probability_calibration_to_dict(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.generic):
        return value.item()
    return value

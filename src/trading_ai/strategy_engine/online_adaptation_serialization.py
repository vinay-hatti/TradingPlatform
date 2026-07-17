from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any


def online_adaptation_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return online_adaptation_to_dict(asdict(value))
    if isinstance(value, dict):
        return {str(k): online_adaptation_to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [online_adaptation_to_dict(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    return value

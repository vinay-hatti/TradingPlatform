from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any


def execution_champion_challenger_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return execution_champion_challenger_to_dict(asdict(value))
    if isinstance(value, dict):
        return {str(k): execution_champion_challenger_to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [execution_champion_challenger_to_dict(v) for v in value]
    if isinstance(value, Enum):
        return execution_champion_challenger_to_dict(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)

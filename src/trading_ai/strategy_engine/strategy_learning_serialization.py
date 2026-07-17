from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any
import json


def strategy_learning_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return strategy_learning_to_dict(asdict(value))
    if isinstance(value, dict):
        return {str(key): strategy_learning_to_dict(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [strategy_learning_to_dict(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def strategy_learning_to_json(value: Any, *, indent: int = 2) -> str:
    return json.dumps(strategy_learning_to_dict(value), indent=indent, sort_keys=True)


def save_strategy_learning(value: Any, path: str | Path, *, indent: int = 2) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(strategy_learning_to_json(value, indent=indent), encoding="utf-8")
    return output

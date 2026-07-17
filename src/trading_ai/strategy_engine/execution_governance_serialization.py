from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any


def execution_governance_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return execution_governance_to_dict(asdict(value))
    if isinstance(value, dict):
        return {str(key): execution_governance_to_dict(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [execution_governance_to_dict(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    try:
        if hasattr(value, "item"):
            return value.item()
    except Exception:
        pass
    return value

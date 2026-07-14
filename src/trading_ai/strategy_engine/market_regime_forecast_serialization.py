from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

import numpy as np


def market_regime_forecast_to_dict(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return "INF" if value > 0 else "-INF"
    if is_dataclass(value):
        return market_regime_forecast_to_dict(asdict(value))
    if isinstance(value, dict):
        return {
            str(key): market_regime_forecast_to_dict(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [market_regime_forecast_to_dict(item) for item in value]
    return value

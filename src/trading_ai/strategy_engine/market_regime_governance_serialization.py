from dataclasses import asdict, is_dataclass
from enum import Enum


def market_regime_governance_to_dict(value):
    if is_dataclass(value):
        return market_regime_governance_to_dict(asdict(value))
    if isinstance(value, dict):
        return {str(k): market_regime_governance_to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [market_regime_governance_to_dict(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    try:
        if hasattr(value, "item"):
            return value.item()
    except Exception:
        pass
    return value

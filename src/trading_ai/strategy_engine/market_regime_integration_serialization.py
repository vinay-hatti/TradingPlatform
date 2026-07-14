from dataclasses import asdict, is_dataclass
from enum import Enum

def market_regime_integration_to_dict(value):
    if is_dataclass(value): return {k:market_regime_integration_to_dict(v) for k,v in asdict(value).items()}
    if isinstance(value,dict): return {str(k):market_regime_integration_to_dict(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [market_regime_integration_to_dict(v) for v in value]
    if isinstance(value,Enum): return value.value
    if hasattr(value,"item"):
        try:return value.item()
        except Exception:pass
    return value

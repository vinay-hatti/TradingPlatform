from dataclasses import asdict, is_dataclass
from enum import Enum


def probability_calibration_ranking_to_dict(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return probability_calibration_ranking_to_dict(asdict(value))
    if isinstance(value, dict):
        return {str(k): probability_calibration_ranking_to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [probability_calibration_ranking_to_dict(v) for v in value]
    if hasattr(value, "item"):
        try: return value.item()
        except Exception: pass
    return str(value)

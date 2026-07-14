from dataclasses import asdict, is_dataclass
from enum import Enum


def probability_calibration_to_dict(value):
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            key: probability_calibration_to_dict(item)
            for key, item in asdict(value).items()
        }
    if isinstance(value, dict):
        return {
            str(key): probability_calibration_to_dict(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [probability_calibration_to_dict(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value

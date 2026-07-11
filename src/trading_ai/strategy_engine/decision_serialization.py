from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum


def serialize_value(value):
    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    if isinstance(value, Enum):
        return value.value

    if isinstance(
        value,
        (
            date,
            datetime,
        ),
    ):
        return value.isoformat()

    if is_dataclass(value):
        return {
            key: serialize_value(item)
            for key, item in asdict(value).items()
        }

    if isinstance(value, dict):
        return {
            str(key): serialize_value(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        return [
            serialize_value(item)
            for item in value
        ]

    if hasattr(value, "__dict__"):
        return {
            key: serialize_value(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }

    return str(value)


def decision_to_dict(decision):
    return serialize_value(decision)


def decision_run_to_dict(result):
    return serialize_value(result)

from __future__ import annotations

import csv
import json
from dataclasses import asdict, is_dataclass
from datetime import date
from enum import Enum
from pathlib import Path

from .completeness import UniverseCompletenessProfile


def _json_value(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def write_completeness_json(
    profile: UniverseCompletenessProfile,
    path: str | Path,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(_json_value(profile), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return destination


def write_completeness_csv(
    profile: UniverseCompletenessProfile,
    path: str | Path,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "symbol",
        "window_start",
        "window_end",
        "expected_trading_days",
        "observed_trading_days",
        "missing_trading_day_count",
        "missing_trading_days",
        "duplicate_row_count",
        "weekend_row_count",
        "weekend_row_dates",
        "holiday_row_count",
        "holiday_row_dates",
        "continuity_percentage",
        "status",
        "warnings",
        "rejection_reasons",
    ]
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in profile.symbol_profiles:
            writer.writerow(
                {
                    "symbol": item.symbol,
                    "window_start": item.window_start.isoformat(),
                    "window_end": item.window_end.isoformat(),
                    "expected_trading_days": item.expected_trading_days,
                    "observed_trading_days": item.observed_trading_days,
                    "missing_trading_day_count": len(item.missing_trading_days),
                    "missing_trading_days": ";".join(
                        value.isoformat() for value in item.missing_trading_days
                    ),
                    "duplicate_row_count": item.duplicate_row_count,
                    "weekend_row_count": len(item.weekend_row_dates),
                    "weekend_row_dates": ";".join(
                        value.isoformat() for value in item.weekend_row_dates
                    ),
                    "holiday_row_count": len(item.holiday_row_dates),
                    "holiday_row_dates": ";".join(
                        value.isoformat() for value in item.holiday_row_dates
                    ),
                    "continuity_percentage": item.continuity_percentage,
                    "status": item.status.value,
                    "warnings": " | ".join(item.warnings),
                    "rejection_reasons": " | ".join(item.rejection_reasons),
                }
            )
    return destination

from __future__ import annotations

import csv
import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .contracts import UniverseCoverageProfile
from .freshness import UniverseFreshnessProfile


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if is_dataclass(value):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set)):
        return [_json_value(item) for item in value]
    return value


def coverage_profile_to_dict(profile: UniverseCoverageProfile) -> dict[str, Any]:
    return _json_value(profile)


def freshness_profile_to_dict(profile: UniverseFreshnessProfile) -> dict[str, Any]:
    return _json_value(profile)


def write_coverage_json(profile: UniverseCoverageProfile, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(coverage_profile_to_dict(profile), indent=2, sort_keys=True) + "\n")
    return output


def write_freshness_json(profile: UniverseFreshnessProfile, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(freshness_profile_to_dict(profile), indent=2, sort_keys=True) + "\n")
    return output


def write_symbol_coverage_csv(profile: UniverseCoverageProfile, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ("symbol", "row_count", "trading_day_count", "earliest_date", "latest_date", "has_history", "meets_minimum_history", "status", "reasons")
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in profile.symbol_profiles:
            writer.writerow({
                "symbol": item.symbol,
                "row_count": item.row_count,
                "trading_day_count": item.trading_day_count,
                "earliest_date": item.earliest_date.isoformat() if item.earliest_date else "",
                "latest_date": item.latest_date.isoformat() if item.latest_date else "",
                "has_history": item.has_history,
                "meets_minimum_history": item.meets_minimum_history,
                "status": item.status.value,
                "reasons": "|".join(item.reasons),
            })
    return output


def write_symbol_freshness_csv(profile: UniverseFreshnessProfile, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ("symbol", "latest_bar_date", "expected_latest_trading_date", "staleness_days", "is_stale", "status", "reasons")
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in profile.symbol_profiles:
            writer.writerow({
                "symbol": item.symbol,
                "latest_bar_date": item.latest_bar_date.isoformat() if item.latest_bar_date else "",
                "expected_latest_trading_date": item.expected_latest_trading_date.isoformat(),
                "staleness_days": "" if item.staleness_days is None else item.staleness_days,
                "is_stale": item.is_stale,
                "status": item.status.value,
                "reasons": "|".join(item.reasons),
            })
    return output

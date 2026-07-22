from __future__ import annotations

import csv
import json
from dataclasses import asdict, is_dataclass
from datetime import date
from enum import Enum
from pathlib import Path

from .contracts import OptionValidationResult


def _value(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value):
        return {key: _value(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_value(item) for item in value]
    return value


def option_validation_result_to_dict(
    result: OptionValidationResult,
) -> dict[str, object]:
    return _value(result)


def write_option_validation_json(
    results: tuple[OptionValidationResult, ...]
    | list[OptionValidationResult],
    path: str | Path,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "record_count": len(results),
        "valid_count": sum(result.valid for result in results),
        "invalid_count": sum(not result.valid for result in results),
        "results": [_value(result) for result in results],
    }
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return destination


def write_option_validation_csv(
    results: tuple[OptionValidationResult, ...]
    | list[OptionValidationResult],
    path: str | Path,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "underlying_symbol",
        "expiration_date",
        "strike",
        "option_side",
        "quote_date",
        "provider_symbol",
        "valid",
        "error_count",
        "warning_count",
        "issue_codes",
        "issue_messages",
    ]
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            record = result.record
            writer.writerow(
                {
                    "underlying_symbol": record.identity.underlying_symbol,
                    "expiration_date": record.identity.expiration_date.isoformat(),
                    "strike": record.identity.strike,
                    "option_side": record.identity.option_side.value,
                    "quote_date": record.quote_date.isoformat(),
                    "provider_symbol": record.provider_symbol or "",
                    "valid": result.valid,
                    "error_count": result.error_count,
                    "warning_count": result.warning_count,
                    "issue_codes": ";".join(issue.code for issue in result.issues),
                    "issue_messages": " | ".join(
                        issue.message for issue in result.issues
                    ),
                }
            )
    return destination

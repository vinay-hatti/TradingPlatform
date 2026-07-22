from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .contracts import OptionChainQualityRunProfile


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Unsupported JSON value: {type(value)!r}")


def write_json_atomic(path, profile):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(
            asdict(profile),
            handle,
            indent=2,
            sort_keys=True,
            default=_json_default,
        )
        handle.write("\n")
    os.replace(temporary, output)
    return output


def write_symbol_csv(path, profile):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = (
        "symbol", "quote_date", "governance_status",
        "quote_observation_status", "spread_observation_status",
        "overall_quality_score", "contract_count", "quoted_contracts",
        "traded_contracts", "liquid_contracts", "valid_spread_contracts",
        "crossed_market_contracts", "locked_market_contracts",
        "negative_market_value_contracts", "iv_available_contracts",
        "delta_available_contracts", "full_greeks_contracts",
        "quote_completeness_score", "trade_completeness_score",
        "liquidity_score", "spread_integrity_score",
        "iv_completeness_score", "greeks_completeness_score",
        "average_spread_pct", "median_spread_pct", "maximum_spread_pct",
        "governance_reasons", "informational_notes",
    )
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in profile.profiles:
            row = {}
            for field in fieldnames:
                value = getattr(item, field)
                if isinstance(value, Enum):
                    value = value.value
                elif isinstance(value, date):
                    value = value.isoformat()
                elif isinstance(value, tuple):
                    value = " | ".join(value)
                row[field] = value
            writer.writerow(row)
    return output

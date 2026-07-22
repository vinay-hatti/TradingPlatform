from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .contracts import OptionChainCoverageRunProfile


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Unsupported JSON value: {type(value)!r}")


def write_json_atomic(
    path: str | Path,
    profile: OptionChainCoverageRunProfile,
) -> Path:
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


def write_symbol_csv(
    path: str | Path,
    profile: OptionChainCoverageRunProfile,
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = (
        "symbol",
        "quote_date",
        "governance_status",
        "overall_coverage_score",
        "contract_count",
        "call_count",
        "put_count",
        "call_put_ratio",
        "call_put_balance_score",
        "expiration_count",
        "expiration_coverage_score",
        "distinct_strike_count",
        "strike_surface_score",
        "minimum_expiration",
        "maximum_expiration",
        "minimum_dte",
        "maximum_dte",
        "governance_reasons",
    )

    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for item in profile.profiles:
            writer.writerow(
                {
                    "symbol": item.symbol,
                    "quote_date": item.quote_date.isoformat(),
                    "governance_status": item.governance_status.value,
                    "overall_coverage_score": item.overall_coverage_score,
                    "contract_count": item.contract_count,
                    "call_count": item.call_count,
                    "put_count": item.put_count,
                    "call_put_ratio": item.call_put_ratio,
                    "call_put_balance_score": item.call_put_balance_score,
                    "expiration_count": item.expiration_count,
                    "expiration_coverage_score": item.expiration_coverage_score,
                    "distinct_strike_count": item.distinct_strike_count,
                    "strike_surface_score": item.strike_surface_score,
                    "minimum_expiration": (
                        item.minimum_expiration.isoformat()
                        if item.minimum_expiration
                        else ""
                    ),
                    "maximum_expiration": (
                        item.maximum_expiration.isoformat()
                        if item.maximum_expiration
                        else ""
                    ),
                    "minimum_dte": item.minimum_dte,
                    "maximum_dte": item.maximum_dte,
                    "governance_reasons": " | ".join(item.governance_reasons),
                }
            )

    return output


def write_expiration_csv(
    path: str | Path,
    profile: OptionChainCoverageRunProfile,
) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = (
        "symbol",
        "quote_date",
        "expiration_date",
        "days_to_expiration",
        "contract_count",
        "call_count",
        "put_count",
        "distinct_strikes",
        "minimum_strike",
        "maximum_strike",
        "median_strike_gap",
        "maximum_strike_gap",
        "strike_gap_completeness_score",
        "call_put_balance_score",
        "completeness_score",
    )

    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for symbol_profile in profile.profiles:
            for item in symbol_profile.expirations:
                writer.writerow(
                    {
                        "symbol": symbol_profile.symbol,
                        "quote_date": symbol_profile.quote_date.isoformat(),
                        "expiration_date": item.expiration_date.isoformat(),
                        "days_to_expiration": item.days_to_expiration,
                        "contract_count": item.contract_count,
                        "call_count": item.call_count,
                        "put_count": item.put_count,
                        "distinct_strikes": item.distinct_strikes,
                        "minimum_strike": item.minimum_strike,
                        "maximum_strike": item.maximum_strike,
                        "median_strike_gap": item.median_strike_gap,
                        "maximum_strike_gap": item.maximum_strike_gap,
                        "strike_gap_completeness_score": (
                            item.strike_gap_completeness_score
                        ),
                        "call_put_balance_score": item.call_put_balance_score,
                        "completeness_score": item.completeness_score,
                    }
                )

    return output

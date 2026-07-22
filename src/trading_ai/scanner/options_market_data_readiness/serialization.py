from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any


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
        "symbol",
        "as_of_date",
        "coverage_status",
        "quality_status",
        "readiness_status",
        "coverage_score",
        "quality_score",
        "readiness_score",
        "contract_count",
        "expiration_count",
        "distinct_strike_count",
        "quote_data_observed",
        "provider_capability_limited",
        "coverage_reasons",
        "quality_reasons",
        "readiness_reasons",
        "informational_notes",
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

from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


def _default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Unsupported JSON value: {type(value)!r}")


def write_jsonl_atomic(path, records: Iterable) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")

    with temporary.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(
                json.dumps(
                    asdict(record),
                    sort_keys=True,
                    default=_default,
                )
            )
            handle.write("\n")

    os.replace(temporary, output)
    return output


def write_json_atomic(path, value) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")

    payload = asdict(value) if hasattr(value, "__dataclass_fields__") else value
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(
            payload,
            handle,
            indent=2,
            sort_keys=True,
            default=_default,
        )
        handle.write("\n")

    os.replace(temporary, output)
    return output


def read_csv_rows(path) -> list[dict[str, str]]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    with source.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))

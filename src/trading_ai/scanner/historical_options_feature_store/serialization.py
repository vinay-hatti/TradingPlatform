from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Unsupported JSON value: {type(value)!r}")


def write_feature_jsonl_atomic(path, records: Iterable) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")

    with temporary.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(
                json.dumps(
                    asdict(record),
                    sort_keys=True,
                    default=_json_default,
                )
            )
            handle.write("\n")

    os.replace(temporary, output)
    return output


def write_run_json_atomic(path, profile) -> Path:
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

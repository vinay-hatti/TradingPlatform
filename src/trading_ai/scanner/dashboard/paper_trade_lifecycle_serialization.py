from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .paper_trade_lifecycle_profile import (
    PaperTradeLifecycleRecord,
)


def write_json_atomic(
    path: Path,
    payload: dict[str, Any],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, default=str)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        temp_path = Path(temp_name)
        if temp_path.exists():
            temp_path.unlink()
    return path


def write_lifecycle_record_atomic(
    path: Path,
    record: PaperTradeLifecycleRecord,
) -> Path:
    return write_json_atomic(path, record.to_dict())

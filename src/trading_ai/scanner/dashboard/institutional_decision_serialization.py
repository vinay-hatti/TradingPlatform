from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .institutional_decision_profile import (
    InstitutionalDecisionRecord,
)


def write_institutional_decision_atomic(
    path: Path,
    record: InstitutionalDecisionRecord,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                record.to_dict(),
                handle,
                indent=2,
                default=str,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        temp_path = Path(temp_name)
        if temp_path.exists():
            temp_path.unlink()
    return path

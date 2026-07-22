from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
from typing import Any


def _default(value: Any):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def reconciliation_to_dict(result: Any) -> dict[str, Any]:
    """Serialize reconciliation results while preserving legacy metadata."""
    payload = asdict(result)
    metadata = getattr(result, "metadata", None)
    if metadata is not None:
        payload["metadata"] = dict(metadata)
    return payload


def write_reconciliation_json(result, output_file: str | Path) -> Path:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(reconciliation_to_dict(result), indent=2, default=_default, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path

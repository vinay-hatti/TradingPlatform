from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
import json


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def universe_payload(result) -> dict[str, Any]:
    return _jsonable(asdict(result))


def write_universe_json(result, output_file: str | Path) -> Path:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(universe_payload(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def write_universe_summary(result, output_file: str | Path) -> Path:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    universe = result.universe
    payload = {
        "universe_id": universe.universe_id,
        "name": universe.name,
        "generated_at": universe.generated_at.isoformat(),
        "governance_status": universe.governance_status,
        "received_count": result.received_count,
        "accepted_count": result.accepted_count,
        "rejected_count": result.rejected_count,
        "duplicate_count": result.duplicate_count,
        "options_eligible_count": universe.metadata.get("options_eligible_count", 0),
        "source_names": list(universe.source_names),
        "warnings": list(universe.warnings),
        "rejection_reasons": result.rejection_reasons,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

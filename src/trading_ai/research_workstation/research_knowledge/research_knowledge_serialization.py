from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): _jsonable(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def research_knowledge_payload(profile) -> dict[str, Any]:
    return _jsonable(asdict(profile))


def write_research_knowledge_base(
    profile,
    output_file: str | Path,
) -> Path:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            research_knowledge_payload(profile),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def write_research_index(
    profile,
    output_file: str | Path,
) -> Path:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "knowledge_base_id": profile.knowledge_base_id,
        "generated_at": profile.generated_at.isoformat(),
        "case_count": profile.case_count,
        "record_count": profile.record_count,
        "tag_count": profile.tag_count,
        "governance_status": profile.governance_status,
        "index": _jsonable(asdict(profile.index)),
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path

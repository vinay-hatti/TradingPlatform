from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def institutional_explainability_payload(
    profile,
) -> dict[str, Any]:
    return _jsonable(asdict(profile))


def write_institutional_explainability_report(
    profile,
    output_file: str | Path,
) -> Path:
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            institutional_explainability_payload(profile),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path

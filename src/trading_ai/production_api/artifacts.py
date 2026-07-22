from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArtifactDocument:
    path: Path
    exists: bool
    payload: Any
    modified_at: datetime | None
    age_seconds: float | None
    stale: bool


class ArtifactRepository:
    def __init__(self, max_age_seconds: int = 3600):
        self.max_age_seconds = max_age_seconds

    def read_json(self, path: Path) -> ArtifactDocument:
        if not path.exists():
            return ArtifactDocument(path, False, None, None, None, True)
        stat = path.stat()
        modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        age = max(0.0, (datetime.now(timezone.utc) - modified_at).total_seconds())
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            payload = {"artifact_error": str(exc)}
        return ArtifactDocument(path, True, payload, modified_at, age, age > self.max_age_seconds)

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class ApiAuditEvent:
    event_id: str
    request_id: str
    method: str
    path: str
    status_code: int
    duration_ms: float
    actor: str | None
    occurred_at: str
    metadata: dict[str, Any]


class JsonApiAuditStore:
    def __init__(self, path: Path = Path("reports/m40/api_audit.json")):
        self.path = path
        self._lock = Lock()

    def append(self, event: ApiAuditEvent) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            records: list[dict[str, Any]] = []
            if self.path.exists():
                try:
                    loaded = json.loads(self.path.read_text(encoding="utf-8"))
                    records = loaded if isinstance(loaded, list) else []
                except (OSError, json.JSONDecodeError):
                    records = []
            records.append(asdict(event))
            temp = self.path.with_suffix(self.path.suffix + ".tmp")
            temp.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
            temp.replace(self.path)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

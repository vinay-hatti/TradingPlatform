from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class IngestionManifestStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, object]:
        if not self.path.exists():
            return {"completed_batches": {}, "updated_at": None}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def is_completed(self, batch_id: str) -> bool:
        data = self.load()
        completed = data.get("completed_batches", {})
        return batch_id in completed

    def mark_completed(
        self,
        batch_id: str,
        *,
        metadata: dict[str, object] | None = None,
    ) -> None:
        data = self.load()
        completed = dict(data.get("completed_batches", {}))
        completed[batch_id] = {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        data["completed_batches"] = completed
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write_atomic(data)

    def reset(self) -> None:
        self._write_atomic({"completed_batches": {}, "updated_at": None})

    def _write_atomic(self, data: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.path)

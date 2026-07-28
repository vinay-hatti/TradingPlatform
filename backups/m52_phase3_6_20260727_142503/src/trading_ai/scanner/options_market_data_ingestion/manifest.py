from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class IngestionManifestStore:
    """JSON manifest with backward-compatible legacy completion and snapshot cycles.

    Legacy callers that omit ``cycle_id`` retain the original behavior. Market
    ingestion supplies a unique cycle id so stable provider batch ids are only
    resumed within the same snapshot cycle, never across separate market runs.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    @staticmethod
    def _empty() -> dict[str, object]:
        return {"completed_batches": {}, "cycles": {}, "latest_cycle_id": None, "updated_at": None}

    def load(self) -> dict[str, object]:
        if not self.path.exists():
            return self._empty()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data.setdefault("completed_batches", {})
        data.setdefault("cycles", {})
        data.setdefault("latest_cycle_id", None)
        data.setdefault("updated_at", None)
        return data

    def begin_cycle(self, cycle_id: str, *, metadata: dict[str, object] | None = None) -> None:
        normalized = str(cycle_id or "").strip()
        if not normalized:
            raise ValueError("cycle_id is required")
        data = self.load()
        cycles = dict(data.get("cycles", {}))
        existing = dict(cycles.get(normalized, {}))
        existing.setdefault("started_at", datetime.now(timezone.utc).isoformat())
        existing.setdefault("completed_batches", {})
        existing["metadata"] = {**dict(existing.get("metadata", {})), **(metadata or {})}
        cycles[normalized] = existing
        data["cycles"] = cycles
        data["latest_cycle_id"] = normalized
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write_atomic(data)

    def complete_cycle(self, cycle_id: str, *, metadata: dict[str, object] | None = None) -> None:
        data = self.load()
        cycles = dict(data.get("cycles", {}))
        cycle = dict(cycles.get(cycle_id, {}))
        cycle.setdefault("started_at", datetime.now(timezone.utc).isoformat())
        cycle.setdefault("completed_batches", {})
        cycle["completed_at"] = datetime.now(timezone.utc).isoformat()
        cycle["metadata"] = {**dict(cycle.get("metadata", {})), **(metadata or {})}
        cycles[cycle_id] = cycle
        data["cycles"] = cycles
        data["latest_cycle_id"] = cycle_id
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write_atomic(data)

    def latest_cycle(self) -> dict[str, object] | None:
        data = self.load()
        cycle_id = data.get("latest_cycle_id")
        if not cycle_id:
            return None
        cycle = dict(dict(data.get("cycles", {})).get(str(cycle_id), {}))
        cycle["cycle_id"] = str(cycle_id)
        return cycle

    def is_completed(self, batch_id: str, *, cycle_id: str | None = None) -> bool:
        data = self.load()
        if cycle_id is None:
            return batch_id in data.get("completed_batches", {})
        cycle = dict(data.get("cycles", {})).get(cycle_id, {})
        return batch_id in dict(cycle).get("completed_batches", {})

    def mark_completed(self, batch_id: str, *, metadata: dict[str, object] | None = None, cycle_id: str | None = None) -> None:
        data = self.load()
        entry = {"completed_at": datetime.now(timezone.utc).isoformat(), "metadata": metadata or {}}
        if cycle_id is None:
            completed = dict(data.get("completed_batches", {}))
            completed[batch_id] = entry
            data["completed_batches"] = completed
        else:
            cycles = dict(data.get("cycles", {}))
            cycle = dict(cycles.get(cycle_id, {}))
            cycle.setdefault("started_at", datetime.now(timezone.utc).isoformat())
            completed = dict(cycle.get("completed_batches", {}))
            completed[batch_id] = entry
            cycle["completed_batches"] = completed
            cycles[cycle_id] = cycle
            data["cycles"] = cycles
            data["latest_cycle_id"] = cycle_id
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write_atomic(data)

    def reset(self) -> None:
        self._write_atomic(self._empty())

    def _write_atomic(self, data: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.path)

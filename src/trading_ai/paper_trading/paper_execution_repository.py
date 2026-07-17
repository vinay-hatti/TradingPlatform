from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .paper_execution_profile import (
    PaperExecutionRecord,
    PaperFillProfile,
)


class JsonPaperExecutionRepository:
    """Persistent paper execution history with execution-key idempotency."""

    def __init__(
        self,
        path: str | Path = "data/paper_trading/executions.json",
    ) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, PaperExecutionRecord]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        result: dict[str, PaperExecutionRecord] = {}
        for key, raw in payload.get("executions", {}).items():
            item = dict(raw)
            item["fills"] = tuple(
                PaperFillProfile(**fill)
                for fill in item.get("fills", ())
            )
            result[key] = PaperExecutionRecord(**item)
        return result

    def _save(
        self,
        records: dict[str, PaperExecutionRecord],
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "executions": {
                key: asdict(record)
                for key, record in records.items()
            }
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def get(self, execution_key: str) -> PaperExecutionRecord | None:
        return self._load().get(execution_key)

    def save(self, record: PaperExecutionRecord) -> PaperExecutionRecord:
        records = self._load()
        records[record.execution_key] = record
        self._save(records)
        return record

    def all(self) -> tuple[PaperExecutionRecord, ...]:
        return tuple(self._load().values())

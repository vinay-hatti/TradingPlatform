from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .export_profile import ExportEnvelope


class JsonExportBufferRepository:
    def __init__(
        self,
        path: str | Path = (
            "data/observability/export_buffer.json"
        ),
    ) -> None:
        self.path = Path(path)

    def _load(self) -> dict:
        if not self.path.exists():
            return {"envelopes": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp.replace(self.path)

    def save(self, envelope: ExportEnvelope) -> ExportEnvelope:
        payload = self._load()
        payload["envelopes"][envelope.envelope_id] = asdict(envelope)
        self._save(payload)
        return envelope

    def delete(self, envelope_id: str) -> None:
        payload = self._load()
        payload["envelopes"].pop(envelope_id, None)
        self._save(payload)

    def pending(
        self,
        signal_type: str,
        limit: int,
    ) -> tuple[ExportEnvelope, ...]:
        items = [
            ExportEnvelope(**raw)
            for raw in self._load()["envelopes"].values()
            if raw["signal_type"] == signal_type
            and raw["status"] == "PENDING"
        ]
        return tuple(sorted(
            items,
            key=lambda item: item.created_at,
        )[:limit])

    def count(self, signal_type: str | None = None) -> int:
        values = self._load()["envelopes"].values()
        if signal_type is None:
            return len(tuple(values))
        return sum(
            raw["signal_type"] == signal_type
            for raw in values
        )

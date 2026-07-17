from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .broker_execution_profile import IdempotencyRecordProfile


def canonical_request_hash(value: Any) -> str:
    if hasattr(value, "to_dict"):
        payload = value.to_dict()
    else:
        try:
            payload = asdict(value)
        except TypeError:
            payload = value

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class BrokerIdempotencyRegistry:
    """Persistent replay protection for broker-mutating requests."""

    def __init__(
        self,
        path: str | Path = "config/broker_idempotency_registry.json",
    ) -> None:
        self.path = Path(path)
        self._records: dict[str, IdempotencyRecordProfile] = {}
        if self.path.exists():
            self.load()

    def get(self, key: str) -> IdempotencyRecordProfile | None:
        return self._records.get(str(key))

    def register(
        self,
        record: IdempotencyRecordProfile,
        *,
        replace: bool = False,
    ) -> IdempotencyRecordProfile:
        if record.key in self._records and not replace:
            raise ValueError(f"Idempotency key already exists: {record.key}")
        self._records[record.key] = record
        return record

    def all(self) -> tuple[IdempotencyRecordProfile, ...]:
        return tuple(
            sorted(
                self._records.values(),
                key=lambda item: item.created_at,
            )
        )

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "records": [
                asdict(record)
                for record in self._records.values()
            ]
        }
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return self.path

    def load(self) -> None:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self._records = {}
        for raw in payload.get("records", []):
            record = IdempotencyRecordProfile(**raw)
            self._records[record.key] = record

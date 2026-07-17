from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .secret_governance_profile import SecretInventoryEntryProfile


class SecretInventoryRegistry:
    """Persistent inventory that never stores raw secret values."""

    def __init__(self, path: str | Path = "config/secret_inventory.json") -> None:
        self.path = Path(path)
        self.entries: dict[str, SecretInventoryEntryProfile] = {}
        self.rotation_history: list[dict[str, Any]] = []
        if self.path.exists():
            self.load()

    @staticmethod
    def key(environment: str, name: str) -> str:
        return f"{environment.strip().lower()}::{name.strip()}"

    def register(
        self,
        entry: SecretInventoryEntryProfile,
        *,
        replace: bool = False,
    ) -> SecretInventoryEntryProfile:
        key = self.key(entry.environment, entry.name)
        if key in self.entries and not replace:
            raise ValueError(
                f"Secret inventory entry already exists: {entry.environment}/{entry.name}"
            )
        self.entries[key] = entry
        return entry

    def get(self, environment: str, name: str) -> SecretInventoryEntryProfile | None:
        return self.entries.get(self.key(environment, name))

    def list_environment(self, environment: str) -> tuple[SecretInventoryEntryProfile, ...]:
        normalized = environment.strip().lower()
        return tuple(
            sorted(
                (
                    entry
                    for entry in self.entries.values()
                    if entry.environment.strip().lower() == normalized
                ),
                key=lambda item: item.name,
            )
        )

    def record_rotation(self, event: dict[str, Any]) -> None:
        self.rotation_history.append(dict(event))

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "entries": [asdict(item) for item in self.entries.values()],
            "rotation_history": self.rotation_history,
        }
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return self.path

    def load(self) -> None:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.entries = {}
        for raw in payload.get("entries", []):
            entry = SecretInventoryEntryProfile(**raw)
            self.entries[self.key(entry.environment, entry.name)] = entry
        self.rotation_history = list(payload.get("rotation_history", []))

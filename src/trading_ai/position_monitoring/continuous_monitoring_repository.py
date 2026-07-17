from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .continuous_monitoring_profile import ContinuousMonitoringCycleState


class JsonContinuousMonitoringRepository:
    def __init__(
        self,
        path: str | Path = "data/position_monitoring/continuous_cycles.json",
    ) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, ContinuousMonitoringCycleState]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return {
            key: ContinuousMonitoringCycleState(**value)
            for key, value in raw.get("cycles", {}).items()
        }

    def _save(self, items: dict[str, ContinuousMonitoringCycleState]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                {"cycles": {key: asdict(value) for key, value in items.items()}},
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def save(self, state: ContinuousMonitoringCycleState) -> ContinuousMonitoringCycleState:
        items = self._load()
        items[state.cycle_id] = state
        self._save(items)
        return state

    def get(self, cycle_id: str) -> ContinuousMonitoringCycleState | None:
        return self._load().get(cycle_id)

    def latest_for_account(self, account_id: str) -> ContinuousMonitoringCycleState | None:
        values = [
            value for value in self._load().values()
            if value.account_id == account_id
        ]
        return max(values, key=lambda item: item.started_at) if values else None

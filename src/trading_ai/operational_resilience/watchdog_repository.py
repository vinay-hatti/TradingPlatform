from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
from .watchdog_profile import (
    HealthAlert,
    IncidentEscalation,
    WatchdogCycleState,
)

class JsonWatchdogRepository:
    def __init__(
        self,
        path: str | Path = (
            "data/operational_resilience/watchdog_state.json"
        ),
    ) -> None:
        self.path = Path(path)

    def _load(self) -> dict:
        if not self.path.exists():
            return {"alerts": {}, "escalations": {}, "cycles": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp.replace(self.path)

    def save_alert(self, alert: HealthAlert) -> HealthAlert:
        payload = self._load()
        payload["alerts"][alert.alert_id] = asdict(alert)
        self._save(payload)
        return alert

    def alert_by_fingerprint(self, fingerprint: str) -> HealthAlert | None:
        for raw in self._load()["alerts"].values():
            if raw["fingerprint"] == fingerprint:
                return HealthAlert(**raw)
        return None

    def save_escalation(
        self, escalation: IncidentEscalation
    ) -> IncidentEscalation:
        payload = self._load()
        payload["escalations"][escalation.escalation_id] = asdict(escalation)
        self._save(payload)
        return escalation

    def escalations_for_incident(
        self, incident_id: str
    ) -> tuple[IncidentEscalation, ...]:
        return tuple(
            IncidentEscalation(**raw)
            for raw in self._load()["escalations"].values()
            if raw["incident_id"] == incident_id
        )

    def save_cycle(
        self, cycle: WatchdogCycleState
    ) -> WatchdogCycleState:
        payload = self._load()
        payload["cycles"][cycle.cycle_id] = asdict(cycle)
        self._save(payload)
        return cycle

    def latest_cycle(
        self, environment: str
    ) -> WatchdogCycleState | None:
        matches = [
            WatchdogCycleState(**raw)
            for raw in self._load()["cycles"].values()
            if raw["environment"] == environment
        ]
        return max(
            matches,
            key=lambda item: (item.started_at, item.sequence_number),
        ) if matches else None

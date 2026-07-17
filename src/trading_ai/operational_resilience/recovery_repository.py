from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path

from .recovery_profile import (
    IncidentRecord,
    RecoveryAction,
    RecoveryAuditEntry,
    RecoveryWorkflowState,
    ServiceRestartRecord,
)

class JsonRecoveryRepository:
    def __init__(
        self,
        path: str | Path = (
            "data/operational_resilience/recovery_state.json"
        ),
    ) -> None:
        self.path = Path(path)

    def _load(self) -> dict:
        if not self.path.exists():
            return {
                "workflows": {},
                "incidents": {},
                "audits": [],
                "restarts": {},
            }
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp.replace(self.path)

    @staticmethod
    def _workflow(raw: dict) -> RecoveryWorkflowState:
        item = dict(raw)
        item["actions"] = tuple(
            RecoveryAction(**value) for value in item.get("actions", ())
        )
        if item.get("restart_record"):
            item["restart_record"] = ServiceRestartRecord(
                **item["restart_record"]
            )
        if item.get("incident"):
            item["incident"] = IncidentRecord(**item["incident"])
        return RecoveryWorkflowState(**item)

    def save_workflow(
        self, state: RecoveryWorkflowState
    ) -> RecoveryWorkflowState:
        payload = self._load()
        payload["workflows"][state.workflow_id] = asdict(state)
        self._save(payload)
        return state

    def get_workflow(
        self, workflow_id: str
    ) -> RecoveryWorkflowState | None:
        raw = self._load()["workflows"].get(workflow_id)
        return self._workflow(raw) if raw else None

    def save_incident(
        self, incident: IncidentRecord
    ) -> IncidentRecord:
        payload = self._load()
        payload["incidents"][incident.incident_id] = asdict(incident)
        self._save(payload)
        return incident

    def get_incident(self, incident_id: str) -> IncidentRecord | None:
        raw = self._load()["incidents"].get(incident_id)
        return IncidentRecord(**raw) if raw else None

    def save_restart(
        self, restart: ServiceRestartRecord
    ) -> ServiceRestartRecord:
        payload = self._load()
        payload["restarts"][restart.restart_id] = asdict(restart)
        self._save(payload)
        return restart

    def restarts_for_service(
        self, service_name: str
    ) -> tuple[ServiceRestartRecord, ...]:
        return tuple(
            ServiceRestartRecord(**raw)
            for raw in self._load()["restarts"].values()
            if raw["service_name"] == service_name
        )

    def append_audit(
        self, entry: RecoveryAuditEntry
    ) -> RecoveryAuditEntry:
        payload = self._load()
        payload["audits"].append(asdict(entry))
        self._save(payload)
        return entry

    def audits_for_entity(
        self, entity_id: str
    ) -> tuple[RecoveryAuditEntry, ...]:
        return tuple(
            RecoveryAuditEntry(**raw)
            for raw in self._load()["audits"]
            if raw["entity_id"] == entity_id
        )

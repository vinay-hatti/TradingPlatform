from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
import hashlib

from .recovery_policy import IncidentPolicy
from .recovery_profile import IncidentRecord

class IncidentEngine:
    def __init__(self, policy: IncidentPolicy | None = None) -> None:
        self.policy = policy or IncidentPolicy()
        self.policy.validate()

    def open_incident(
        self,
        *,
        service_name: str,
        environment: str,
        title: str,
        critical: bool,
        workflow_id: str,
        metadata: dict | None = None,
    ) -> IncidentRecord:
        now = datetime.now(timezone.utc)
        incident_id = "incident-" + hashlib.sha256(
            f"{service_name}:{workflow_id}".encode()
        ).hexdigest()[:16]
        return IncidentRecord(
            incident_id=incident_id,
            title=title,
            service_name=service_name,
            environment=environment,
            severity=(
                self.policy.critical_service_severity
                if critical else self.policy.default_severity
            ),
            assigned_role=self.policy.auto_assign_role,
            recovery_workflow_id=workflow_id,
            opened_at=now.isoformat(),
            metadata=metadata or {},
        )

    def acknowledge(
        self,
        incident: IncidentRecord,
        *,
        actor: str,
    ) -> IncidentRecord:
        return replace(
            incident,
            status="ACKNOWLEDGED",
            acknowledged_at=datetime.now(timezone.utc).isoformat(),
            acknowledged_by=actor,
        )

    def resolve(
        self,
        incident: IncidentRecord,
        *,
        note: str,
    ) -> IncidentRecord:
        return replace(
            incident,
            status="RESOLVED",
            resolved_at=datetime.now(timezone.utc).isoformat(),
            resolution_note=note,
        )

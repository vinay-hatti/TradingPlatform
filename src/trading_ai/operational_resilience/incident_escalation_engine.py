from __future__ import annotations
from datetime import datetime, timedelta, timezone
import hashlib
from .recovery_profile import IncidentRecord
from .watchdog_policy import IncidentEscalationPolicy
from .watchdog_profile import IncidentEscalation

class IncidentEscalationEngine:
    TARGETS = {
        1: "ON_CALL_OPERATIONS",
        2: "PLATFORM_OWNER",
        3: "EXECUTIVE_ON_CALL",
    }

    def __init__(
        self,
        policy: IncidentEscalationPolicy | None = None,
    ) -> None:
        self.policy = policy or IncidentEscalationPolicy()
        self.policy.validate()

    def next_escalation(
        self,
        *,
        incident: IncidentRecord,
        existing: tuple[IncidentEscalation, ...],
        as_of: datetime | None = None,
    ) -> IncidentEscalation | None:
        if incident.status == "RESOLVED":
            return None
        now = as_of or datetime.now(timezone.utc)
        level = len(existing) + 1
        if level > self.policy.maximum_escalation_level:
            return None
        delay = (
            self.policy.critical_escalation_seconds
            if incident.severity == "CRITICAL"
            else self.policy.severe_escalation_seconds
        )
        due = now + timedelta(seconds=delay)
        raw = f"{incident.incident_id}:{level}"
        return IncidentEscalation(
            escalation_id="escalation-" + hashlib.sha256(
                raw.encode()
            ).hexdigest()[:16],
            incident_id=incident.incident_id,
            level=level,
            target_role=self.TARGETS.get(level, "EXECUTIVE_ON_CALL"),
            reason=f"{incident.severity}_INCIDENT_UNRESOLVED",
            created_at=now.isoformat(),
            due_at=due.isoformat(),
        )

from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from .watchdog_policy import HealthAlertRoutingPolicy
from .watchdog_profile import HealthAlert
from .watchdog_repository import JsonWatchdogRepository

def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

class HealthAlertRouter:
    def __init__(
        self,
        *,
        policy: HealthAlertRoutingPolicy | None = None,
        repository: JsonWatchdogRepository | None = None,
    ) -> None:
        self.policy = policy or HealthAlertRoutingPolicy()
        self.policy.validate()
        self.repository = repository or JsonWatchdogRepository()

    def _channels(self, severity: str) -> tuple[str, ...]:
        value = severity.upper()
        if value == "CRITICAL":
            return self.policy.critical_channels
        if value in {"SEVERE", "HIGH"}:
            return self.policy.severe_channels
        return self.policy.warning_channels

    def route(
        self,
        *,
        service_name: str,
        environment: str,
        severity: str,
        title: str,
        message: str,
        incident_id: str | None = None,
        metadata: dict | None = None,
        as_of: datetime | None = None,
    ) -> HealthAlert:
        now = as_of or datetime.now(timezone.utc)
        fingerprint = hashlib.sha256(
            f"{environment}:{service_name}:{severity}:{title}".encode()
        ).hexdigest()
        existing = self.repository.alert_by_fingerprint(fingerprint)
        if existing and (
            now - _parse(existing.last_detected_at)
        ).total_seconds() <= self.policy.deduplication_window_seconds:
            alert = replace(
                existing,
                occurrence_count=existing.occurrence_count + 1,
                last_detected_at=now.isoformat(),
                message=message,
                incident_id=incident_id or existing.incident_id,
                metadata={**existing.metadata, **(metadata or {})},
            )
        else:
            alert = HealthAlert(
                alert_id="health-alert-" + fingerprint[:16],
                fingerprint=fingerprint,
                service_name=service_name,
                environment=environment,
                severity=severity.upper(),
                title=title,
                message=message,
                channels=self._channels(severity),
                first_detected_at=now.isoformat(),
                last_detected_at=now.isoformat(),
                incident_id=incident_id,
                metadata=metadata or {},
            )
        if self.policy.persist_alerts:
            self.repository.save_alert(alert)
        return alert

    def mark_sent(
        self,
        alert: HealthAlert,
        *,
        as_of: datetime | None = None,
    ) -> HealthAlert:
        now = as_of or datetime.now(timezone.utc)
        updated = replace(
            alert,
            status="SENT",
            sent_at=now.isoformat(),
        )
        self.repository.save_alert(updated)
        return updated

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib

from .alert_rule_policy import AlertRule, AlertRulePolicy
from .slo_profile import ObservabilityAlert


class AlertRuleEngine:
    def __init__(
        self,
        policy: AlertRulePolicy | None = None,
    ) -> None:
        self.policy = policy or AlertRulePolicy()
        self._alerts: dict[str, ObservabilityAlert] = {}
        self._breaches: dict[str, int] = {}

    @staticmethod
    def _matches(value: float, rule: AlertRule) -> bool:
        return {
            "GREATER_THAN": value > rule.threshold,
            "GREATER_THAN_OR_EQUAL": value >= rule.threshold,
            "LESS_THAN": value < rule.threshold,
            "LESS_THAN_OR_EQUAL": value <= rule.threshold,
            "EQUAL": value == rule.threshold,
        }[rule.comparison]

    @staticmethod
    def _fingerprint(
        rule: AlertRule,
        service_name: str,
        environment: str,
    ) -> str:
        raw = f"{rule.rule_id}:{service_name}:{environment}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def evaluate(
        self,
        *,
        rule: AlertRule,
        value: float,
        service_name: str,
        environment: str,
        fields: dict | None = None,
        as_of: datetime | None = None,
    ) -> ObservabilityAlert | None:
        rule.validate()
        if not rule.enabled:
            return None
        fingerprint = self._fingerprint(
            rule, service_name, environment
        )
        if not self._matches(value, rule):
            self._breaches[fingerprint] = 0
            return None

        self._breaches[fingerprint] = (
            self._breaches.get(fingerprint, 0) + 1
        )
        if (
            self._breaches[fingerprint]
            < rule.consecutive_breaches
        ):
            return None

        now = as_of or datetime.now(timezone.utc)
        now_iso = now.isoformat()
        existing = self._alerts.get(fingerprint)
        if existing and self.policy.deduplicate:
            updated = replace(
                existing,
                occurrence_count=existing.occurrence_count + 1,
                last_seen_at=now_iso,
                fields={**existing.fields, **(fields or {})},
            )
            self._alerts[fingerprint] = updated
            return updated

        alert = ObservabilityAlert(
            alert_id=f"obs-alert-{fingerprint}",
            rule_id=rule.rule_id,
            service_name=service_name,
            environment=environment,
            severity=rule.severity,
            status=self.policy.default_status,
            summary=(
                f"{rule.signal_type} breached: "
                f"{value} {rule.comparison} {rule.threshold}"
            ),
            fingerprint=fingerprint,
            first_seen_at=now_iso,
            last_seen_at=now_iso,
            fields={"value": value, **(fields or {})},
        )
        self._alerts[fingerprint] = alert
        return alert

    def acknowledge(
        self,
        fingerprint: str,
        at: datetime | None = None,
    ) -> ObservabilityAlert:
        alert = self._alerts[fingerprint]
        updated = replace(
            alert,
            status="ACKNOWLEDGED",
            acknowledged_at=(at or datetime.now(
                timezone.utc
            )).isoformat(),
        )
        self._alerts[fingerprint] = updated
        return updated

    def resolve(
        self,
        fingerprint: str,
        at: datetime | None = None,
    ) -> ObservabilityAlert:
        alert = self._alerts[fingerprint]
        updated = replace(
            alert,
            status="RESOLVED",
            resolved_at=(at or datetime.now(
                timezone.utc
            )).isoformat(),
        )
        self._alerts[fingerprint] = updated
        return updated

    def alerts(self) -> tuple[ObservabilityAlert, ...]:
        return tuple(self._alerts.values())

from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from trading_ai.ui.models.observability import (
    AlertRecord,
    AlertSeverity,
    HealthCheckResult,
    HealthStatus,
    ObservabilityState,
    ObservabilitySummary,
)
from trading_ai.ui.observability.metrics_registry import MetricsRegistry


class ObservabilityService:
    def __init__(
        self,
        *,
        metrics: MetricsRegistry | None = None,
        log_path: Path | str = "reports/observability/workstation.jsonl",
        alert_path: Path | str = "reports/observability/alerts.json",
        command_state_path: Path | str = "reports/ui/paper_trading_state.json",
        broker_state_path: Path | str = "reports/ui/paper_broker_state.json",
        minimum_free_disk_mb: float = 100.0,
    ):
        self.metrics = metrics or MetricsRegistry.shared()
        self.log_path = Path(log_path)
        self.alert_path = Path(alert_path)
        self.command_state_path = Path(command_state_path)
        self.broker_state_path = Path(broker_state_path)
        self.minimum_free_disk_mb = minimum_free_disk_mb

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    def _timed_check(self, name, required, function):
        started = time.perf_counter()
        try:
            status, detail = function()
        except Exception as error:
            status, detail = HealthStatus.UNHEALTHY, str(error)
        latency = (time.perf_counter() - started) * 1000
        self.metrics.gauge(
            "health_check_latency_ms",
            latency,
            labels={"check": name},
        )
        return HealthCheckResult(
            name=name,
            status=status,
            required=required,
            detail=detail,
            latency_ms=round(latency, 3),
            observed_at=self._now(),
        )

    def health_checks(self) -> list[HealthCheckResult]:
        def process_check():
            return HealthStatus.HEALTHY, f"Process {os.getpid()} is running."

        def log_path_check():
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            writable = os.access(self.log_path.parent, os.W_OK)
            return (
                (HealthStatus.HEALTHY, "Structured log directory is writable.")
                if writable
                else (HealthStatus.UNHEALTHY, "Structured log directory is not writable.")
            )

        def command_state_check():
            if not self.command_state_path.exists():
                return HealthStatus.DEGRADED, "Paper command state has not been created yet."
            json.loads(self.command_state_path.read_text(encoding="utf-8"))
            return HealthStatus.HEALTHY, "Paper command state is readable."

        def broker_state_check():
            if not self.broker_state_path.exists():
                return HealthStatus.DEGRADED, "Paper broker state has not been created yet."
            json.loads(self.broker_state_path.read_text(encoding="utf-8"))
            return HealthStatus.HEALTHY, "Paper broker state is readable."

        def disk_check():
            usage = shutil.disk_usage(Path.cwd())
            free_mb = usage.free / (1024 * 1024)
            if free_mb < self.minimum_free_disk_mb:
                return (
                    HealthStatus.UNHEALTHY,
                    f"Free disk {free_mb:.1f} MB is below {self.minimum_free_disk_mb:.1f} MB.",
                )
            return HealthStatus.HEALTHY, f"Free disk: {free_mb:.1f} MB."

        return [
            self._timed_check("process", True, process_check),
            self._timed_check("structured_logging", True, log_path_check),
            self._timed_check("paper_command_state", False, command_state_check),
            self._timed_check("paper_broker_state", False, broker_state_check),
            self._timed_check("disk_space", True, disk_check),
        ]

    @staticmethod
    def _aggregate(checks, required_only=False):
        candidates = [
            check for check in checks if check.required or not required_only
        ]
        if any(check.status == HealthStatus.UNHEALTHY for check in candidates):
            return HealthStatus.UNHEALTHY
        if any(check.status == HealthStatus.DEGRADED for check in candidates):
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def _load_alerts(self) -> list[AlertRecord]:
        if not self.alert_path.exists():
            return []
        payload = json.loads(self.alert_path.read_text(encoding="utf-8"))
        return [AlertRecord.model_validate(item) for item in payload.get("alerts", [])]

    def _save_alerts(self, alerts: list[AlertRecord]):
        self.alert_path.parent.mkdir(parents=True, exist_ok=True)
        self.alert_path.write_text(
            json.dumps(
                {"alerts": [item.model_dump(mode="json") for item in alerts]},
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def evaluate_alerts(
        self,
        checks: list[HealthCheckResult],
    ) -> list[AlertRecord]:
        existing = self._load_alerts()
        active_by_rule = {
            alert.rule_name: alert
            for alert in existing
            if alert.status == "ACTIVE"
        }
        now = self._now()
        active_rules: set[str] = set()

        for check in checks:
            if check.status == HealthStatus.HEALTHY:
                continue
            rule = f"health.{check.name}"
            active_rules.add(rule)
            severity = (
                AlertSeverity.CRITICAL
                if check.status == HealthStatus.UNHEALTHY and check.required
                else AlertSeverity.WARNING
            )
            alert = active_by_rule.get(rule)
            if alert:
                alert.last_seen_at = now
                alert.message = check.detail
                alert.severity = severity
            else:
                existing.append(
                    AlertRecord(
                        alert_id=f"alert-{uuid4().hex[:16]}",
                        rule_name=rule,
                        severity=severity,
                        status="ACTIVE",
                        message=check.detail,
                        source=check.name,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                )

        for alert in existing:
            if alert.status == "ACTIVE" and alert.rule_name not in active_rules:
                alert.status = "RESOLVED"
                alert.last_seen_at = now

        self._save_alerts(existing)
        self.metrics.gauge(
            "active_alerts",
            sum(alert.status == "ACTIVE" for alert in existing),
        )
        return existing

    def acknowledge(self, alert_id: str, actor: str, reason: str) -> AlertRecord:
        alerts = self._load_alerts()
        alert = next((item for item in alerts if item.alert_id == alert_id), None)
        if alert is None:
            raise KeyError(alert_id)
        alert.acknowledged = True
        alert.acknowledged_by = actor
        alert.acknowledged_at = self._now()
        alert.message = f"{alert.message} | Acknowledged: {reason}"
        self._save_alerts(alerts)
        return alert

    def state(self) -> ObservabilityState:
        checks = self.health_checks()
        alerts = self.evaluate_alerts(checks)
        active = [alert for alert in alerts if alert.status == "ACTIVE"]
        readiness = self._aggregate(checks, required_only=True)
        liveness = next(
            check.status for check in checks if check.name == "process"
        )
        service_status = self._aggregate(checks)
        metrics = self.metrics.snapshot()

        return ObservabilityState(
            generated_at=self._now(),
            summary=ObservabilitySummary(
                service_status=service_status,
                readiness_status=readiness,
                liveness_status=liveness,
                metric_count=len(metrics),
                active_alert_count=len(active),
                critical_alert_count=sum(
                    alert.severity == AlertSeverity.CRITICAL
                    for alert in active
                ),
                warning_alert_count=sum(
                    alert.severity == AlertSeverity.WARNING
                    for alert in active
                ),
                structured_log_path=str(self.log_path),
            ),
            metrics=metrics,
            health_checks=checks,
            alerts=sorted(
                alerts,
                key=lambda alert: alert.last_seen_at,
                reverse=True,
            ),
            notices=[
                "Metrics are process-local and reset on restart.",
                "Structured logs are written as JSON Lines.",
                "Alerts are persisted locally and require explicit acknowledgement.",
            ],
        )

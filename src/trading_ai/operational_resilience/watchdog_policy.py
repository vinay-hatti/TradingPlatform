from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class HealthAlertRoutingPolicy:
    warning_channels: tuple[str, ...] = ("LOG",)
    severe_channels: tuple[str, ...] = ("LOG", "EMAIL")
    critical_channels: tuple[str, ...] = ("LOG", "EMAIL", "PAGER")
    deduplication_window_seconds: float = 300.0
    persist_alerts: bool = True

    def validate(self) -> None:
        if self.deduplication_window_seconds < 0:
            raise ValueError("deduplication_window_seconds cannot be negative")
        if not self.warning_channels:
            raise ValueError("warning_channels cannot be empty")
        if not self.severe_channels:
            raise ValueError("severe_channels cannot be empty")
        if not self.critical_channels:
            raise ValueError("critical_channels cannot be empty")

@dataclass(frozen=True)
class IncidentEscalationPolicy:
    severe_escalation_seconds: float = 900.0
    critical_escalation_seconds: float = 300.0
    maximum_escalation_level: int = 3
    persist_escalations: bool = True

    def validate(self) -> None:
        if self.severe_escalation_seconds <= 0:
            raise ValueError("severe_escalation_seconds must be positive")
        if self.critical_escalation_seconds <= 0:
            raise ValueError("critical_escalation_seconds must be positive")
        if self.maximum_escalation_level <= 0:
            raise ValueError("maximum_escalation_level must be positive")

@dataclass(frozen=True)
class OperationalWatchdogPolicy:
    cycle_interval_seconds: float = 15.0
    maximum_cycle_duration_seconds: float = 60.0
    maximum_consecutive_cycle_failures: int = 3
    invoke_recovery_on_not_ready: bool = True
    invoke_recovery_on_critical_health: bool = True
    create_incident_when_recovery_fails: bool = True
    require_health_state: bool = True
    persist_cycles: bool = True
    fail_closed: bool = True

    def validate(self) -> None:
        if self.cycle_interval_seconds <= 0:
            raise ValueError("cycle_interval_seconds must be positive")
        if self.maximum_cycle_duration_seconds <= 0:
            raise ValueError("maximum_cycle_duration_seconds must be positive")
        if self.maximum_consecutive_cycle_failures <= 0:
            raise ValueError(
                "maximum_consecutive_cycle_failures must be positive"
            )

@dataclass(frozen=True)
class WatchdogGovernancePolicy:
    alerts: HealthAlertRoutingPolicy = HealthAlertRoutingPolicy()
    escalation: IncidentEscalationPolicy = IncidentEscalationPolicy()
    watchdog: OperationalWatchdogPolicy = OperationalWatchdogPolicy()

    def validate(self) -> None:
        self.alerts.validate()
        self.escalation.validate()
        self.watchdog.validate()

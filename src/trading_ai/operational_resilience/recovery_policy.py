from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class RecoveryWorkflowPolicy:
    maximum_recovery_attempts: int = 3
    recovery_cooldown_seconds: float = 30.0
    verification_timeout_seconds: float = 60.0
    require_post_recovery_health_check: bool = True
    open_incident_on_exhaustion: bool = True
    persist_workflow_state: bool = True
    fail_closed: bool = True

    def validate(self) -> None:
        if self.maximum_recovery_attempts <= 0:
            raise ValueError("maximum_recovery_attempts must be positive")
        if self.recovery_cooldown_seconds < 0:
            raise ValueError("recovery_cooldown_seconds cannot be negative")
        if self.verification_timeout_seconds <= 0:
            raise ValueError("verification_timeout_seconds must be positive")

@dataclass(frozen=True)
class ServiceRestartPolicy:
    maximum_restarts_per_window: int = 3
    restart_window_seconds: float = 900.0
    minimum_restart_interval_seconds: float = 60.0
    require_manual_approval_for_critical_services: bool = False
    allow_automatic_restart: bool = True
    restart_timeout_seconds: float = 120.0
    fail_closed: bool = True

    def validate(self) -> None:
        if self.maximum_restarts_per_window <= 0:
            raise ValueError("maximum_restarts_per_window must be positive")
        if self.restart_window_seconds <= 0:
            raise ValueError("restart_window_seconds must be positive")
        if self.minimum_restart_interval_seconds < 0:
            raise ValueError("minimum_restart_interval_seconds cannot be negative")
        if self.restart_timeout_seconds <= 0:
            raise ValueError("restart_timeout_seconds must be positive")

@dataclass(frozen=True)
class IncidentPolicy:
    default_severity: str = "SEVERE"
    critical_service_severity: str = "CRITICAL"
    auto_assign_role: str = "ON_CALL_OPERATIONS"
    acknowledge_timeout_seconds: float = 300.0
    resolution_timeout_seconds: float = 3600.0
    persist_incidents: bool = True

    def validate(self) -> None:
        allowed = {"LOW", "MODERATE", "SEVERE", "CRITICAL"}
        if self.default_severity not in allowed:
            raise ValueError("invalid default_severity")
        if self.critical_service_severity not in allowed:
            raise ValueError("invalid critical_service_severity")
        if self.acknowledge_timeout_seconds <= 0:
            raise ValueError("acknowledge_timeout_seconds must be positive")
        if self.resolution_timeout_seconds <= 0:
            raise ValueError("resolution_timeout_seconds must be positive")

@dataclass(frozen=True)
class RecoveryGovernancePolicy:
    workflow: RecoveryWorkflowPolicy = RecoveryWorkflowPolicy()
    restart: ServiceRestartPolicy = ServiceRestartPolicy()
    incident: IncidentPolicy = IncidentPolicy()

    def validate(self) -> None:
        self.workflow.validate()
        self.restart.validate()
        self.incident.validate()

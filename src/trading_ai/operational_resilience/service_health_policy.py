from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceHealthPolicy:
    """Govern service heartbeats, dependency readiness, and health scoring."""

    heartbeat_stale_after_seconds: int = 30
    heartbeat_dead_after_seconds: int = 120
    dependency_stale_after_seconds: int = 60
    maximum_consecutive_failures: int = 3
    maximum_degraded_dependencies: int = 1
    require_critical_services: bool = True
    require_critical_dependencies: bool = True
    reject_unknown_service_state: bool = True
    reject_unknown_dependency_state: bool = True
    persist_runtime_health: bool = True
    minimum_ready_score: float = 85.0
    minimum_healthy_score: float = 95.0
    fail_closed: bool = True

    def validate(self) -> None:
        if self.heartbeat_stale_after_seconds <= 0:
            raise ValueError(
                "heartbeat_stale_after_seconds must be positive"
            )
        if (
            self.heartbeat_dead_after_seconds
            <= self.heartbeat_stale_after_seconds
        ):
            raise ValueError(
                "heartbeat_dead_after_seconds must exceed stale threshold"
            )
        if self.dependency_stale_after_seconds <= 0:
            raise ValueError(
                "dependency_stale_after_seconds must be positive"
            )
        if self.maximum_consecutive_failures <= 0:
            raise ValueError(
                "maximum_consecutive_failures must be positive"
            )
        if self.maximum_degraded_dependencies < 0:
            raise ValueError(
                "maximum_degraded_dependencies cannot be negative"
            )
        for name in ("minimum_ready_score", "minimum_healthy_score"):
            value = getattr(self, name)
            if not 0 <= value <= 100:
                raise ValueError(f"{name} must be between 0 and 100")
        if self.minimum_healthy_score < self.minimum_ready_score:
            raise ValueError(
                "minimum_healthy_score cannot be below minimum_ready_score"
            )

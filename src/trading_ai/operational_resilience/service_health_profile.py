from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ServiceHeartbeat:
    service_name: str
    instance_id: str
    environment: str
    status: str
    timestamp: str = field(default_factory=utc_now_iso)
    sequence: int = 0
    version: str | None = None
    host: str | None = None
    process_id: int | None = None
    critical: bool = True
    consecutive_failures: int = 0
    latency_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DependencyHealth:
    dependency_name: str
    dependency_type: str
    status: str
    checked_at: str = field(default_factory=utc_now_iso)
    critical: bool = True
    latency_ms: float | None = None
    consecutive_failures: int = 0
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ServiceHealthSnapshot:
    service_name: str
    instance_id: str
    environment: str
    status: str
    heartbeat_age_seconds: float
    heartbeat_fresh: bool
    ready: bool
    healthy: bool
    score: float
    critical: bool
    dependencies: tuple[DependencyHealth, ...] = ()
    degraded_dependencies: tuple[str, ...] = ()
    failed_dependencies: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeHealthState:
    registry_id: str
    environment: str
    overall_status: str
    ready: bool
    healthy: bool
    score: float
    service_count: int
    ready_service_count: int
    healthy_service_count: int
    degraded_service_count: int
    failed_service_count: int
    critical_failure_count: int
    services: tuple[ServiceHealthSnapshot, ...] = ()
    version: int = 1
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeHealthCheck:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeHealthDecision:
    valid: bool
    allowed: bool
    registry_id: str
    environment: str
    score: float
    grade: str
    severity: str
    recommendation: str
    state: RuntimeHealthState | None = None
    checks: tuple[RuntimeHealthCheck, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

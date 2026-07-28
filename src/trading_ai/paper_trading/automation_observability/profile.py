from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AutomationHealthCheck:
    code: str
    component: str
    status: str
    severity: str
    message: str
    actual: Any = None
    expected: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AutomationIncident:
    incident_id: str
    category: str
    severity: str
    title: str
    description: str
    source_phase: int | None
    source_code: str
    recoverable: bool
    recommended_action: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AutomationTelemetrySnapshot:
    portfolio_id: str
    scheduler_status: str
    control_plane_status: str
    portfolio_health_score: float
    portfolio_health_grade: str
    risk_breach_count: int
    cycle_error_count: int
    cycle_warning_count: int
    completed_phases: int
    failed_phases: int
    retried_phases: int
    active_orders: int
    stale_orders: int
    open_positions: int
    exit_candidates: int
    daily_pnl: float
    net_liquidation_value: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AutomationObservabilityResult:
    milestone: int
    phase: int
    portfolio_id: str
    overall_status: str
    health_score: float
    telemetry: dict[str, Any]
    checks: tuple[dict[str, Any], ...]
    incidents: tuple[dict[str, Any], ...]
    recovery_actions: tuple[str, ...]
    alert_summary: dict[str, Any]
    created_at: str = field(default_factory=utc_now_iso)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

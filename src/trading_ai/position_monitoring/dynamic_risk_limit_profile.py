from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class DynamicRiskLimitProfile:
    profile_id: str
    scope_type: str
    scope_value: str
    metric: str
    warning_limit: float | None
    severe_limit: float | None
    critical_limit: float | None
    direction: str = 'ABSOLUTE_MAX'
    precedence: int = 100
    active: bool = True
    effective_from: str = field(default_factory=utc_now_iso)
    effective_to: str | None = None
    version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ResolvedRiskLimit:
    metric: str
    scope_type: str
    scope_value: str
    profile_id: str
    warning_limit: float | None
    severe_limit: float | None
    critical_limit: float | None
    direction: str
    precedence: int
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class RiskBreachProfile:
    breach_id: str
    account_id: str
    snapshot_id: str
    metric: str
    scope_type: str
    scope_value: str
    observed_value: float
    limit_value: float
    severity: str
    direction: str
    status: str = 'OPEN'
    occurrence_count: int = 1
    first_detected_at: str = field(default_factory=utc_now_iso)
    last_detected_at: str = field(default_factory=utc_now_iso)
    acknowledged_at: str | None = None
    acknowledged_by: str | None = None
    resolved_at: str | None = None
    resolution_note: str | None = None
    escalation_level: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class RiskAlertProfile:
    alert_id: str
    breach_id: str
    account_id: str
    severity: str
    channel: str
    destination: str
    subject: str
    message: str
    status: str = 'PENDING'
    attempt_count: int = 0
    created_at: str = field(default_factory=utc_now_iso)
    sent_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class RiskEscalationProfile:
    escalation_id: str
    breach_id: str
    level: int
    reason: str
    target_role: str
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class RiskBreachMonitoringDecision:
    valid: bool
    allowed: bool
    account_id: str
    snapshot_id: str
    recommendation: str
    breaches: tuple[RiskBreachProfile, ...] = ()
    alerts: tuple[RiskAlertProfile, ...] = ()
    escalations: tuple[RiskEscalationProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

def utc_now_iso() -> str: return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class BrokerPositionDifference:
    symbol: str
    broker_quantity: float
    platform_quantity: float
    quantity_difference: float
    broker_average_cost: float
    platform_average_cost: float
    average_cost_difference: float
    average_cost_difference_pct: float | None
    matched: bool
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class BrokerPositionReconciliationDecision:
    valid: bool
    allowed: bool
    account_id: str
    score: float
    grade: str
    severity: str
    recommendation: str
    differences: tuple[BrokerPositionDifference, ...] = ()
    missing_at_broker: tuple[str, ...] = ()
    missing_at_platform: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    evaluated_at: str = field(default_factory=utc_now_iso)

@dataclass(frozen=True)
class KillSwitchActivationDecision:
    valid: bool
    activated: bool
    account_id: str
    reason: str | None
    source: str
    critical_breach_ids: tuple[str, ...] = ()
    reconciliation_failed: bool = False
    monitoring_failed: bool = False
    control_state: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

@dataclass(frozen=True)
class ContinuousMonitoringCycleState:
    cycle_id: str
    account_id: str
    sequence_number: int
    state: str
    completed_stages: tuple[str, ...] = ()
    failed_stage: str | None = None
    error: str | None = None
    position_snapshot_id: str | None = None
    greeks_snapshot_id: str | None = None
    breach_count: int = 0
    reconciliation_allowed: bool | None = None
    kill_switch_activated: bool = False
    started_at: str = field(default_factory=utc_now_iso)
    completed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ContinuousMonitoringDecision:
    valid: bool
    allowed: bool
    account_id: str
    cycle_id: str
    recommendation: str
    position_decision: Any = None
    greeks_decision: Any = None
    breach_decision: Any = None
    reconciliation_decision: BrokerPositionReconciliationDecision | None = None
    kill_switch_decision: KillSwitchActivationDecision | None = None
    cycle_state: ContinuousMonitoringCycleState | None = None
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)
    def to_dict(self) -> dict[str, Any]: return asdict(self)

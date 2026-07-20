from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class EntryPlanProfile:
    entry_status: str
    entry_allowed: bool
    entry_window: str
    order_type: str
    time_in_force: str
    target_limit_price: float
    maximum_acceptable_price: float
    minimum_credit_or_maximum_debit: float
    confidence: float
    days_to_expiration: int
    rationale: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExitPlanProfile:
    profit_target_value: float
    profit_target_pct: float
    stop_loss_value: float
    maximum_loss_value: float
    time_exit_dte: int
    event_risk_exit_days: int
    expiration_exit_required: bool
    close_order_type: str
    monitoring_frequency: str


@dataclass(frozen=True)
class AdjustmentActionProfile:
    action: str
    priority: int
    trigger: str
    allowed: bool
    target: str
    rationale: str


@dataclass(frozen=True)
class LifecycleCheckpointProfile:
    name: str
    trigger_condition: str
    recommended_action: str
    severity: str
    mandatory: bool


@dataclass(frozen=True)
class TradeLifecycleProfile:
    symbol: str
    strategy_name: str
    entry: EntryPlanProfile
    exit: ExitPlanProfile
    adjustments: tuple[AdjustmentActionProfile, ...]
    checkpoints: tuple[LifecycleCheckpointProfile, ...]
    lifecycle_score: float
    lifecycle_grade: str
    risk_severity: str
    allowed: bool
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

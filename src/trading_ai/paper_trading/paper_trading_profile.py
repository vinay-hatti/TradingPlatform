from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PaperTradingSessionProfile:
    session_id: str
    account_id: str
    environment: str
    strategy_names: tuple[str, ...]
    symbols: tuple[str, ...]
    cycle_interval_seconds: int
    starting_capital: float
    state: str = "CREATED"
    created_at: str = field(default_factory=utc_now_iso)
    started_at: str | None = None
    stopped_at: str | None = None
    last_cycle_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaperTradingCycleProfile:
    cycle_id: str
    session_id: str
    sequence_number: int
    started_at: str
    completed_at: str | None = None
    state: str = "STARTED"
    scanned_symbols: tuple[str, ...] = ()
    candidate_count: int = 0
    approved_count: int = 0
    submitted_count: int = 0
    rejected_count: int = 0
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaperTradingRuntimeState:
    session: PaperTradingSessionProfile
    cycle_count: int = 0
    orders_created: int = 0
    orders_submitted: int = 0
    orders_rejected: int = 0
    fills_received: int = 0
    open_positions: int = 0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    last_cycle: PaperTradingCycleProfile | None = None
    pending_order_ids: tuple[str, ...] = ()
    active_position_ids: tuple[str, ...] = ()
    recovery_required: bool = False
    recovery_reason: str | None = None
    version: int = 1
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PaperTradingCheck:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaperTradingSessionDecision:
    valid: bool
    allowed: bool
    action: str
    session_id: str
    current_state: str
    target_state: str | None
    score: float
    grade: str
    severity: str
    recommendation: str
    checks: tuple[PaperTradingCheck, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

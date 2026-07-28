from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ManagedPaperPosition:
    position_id: str
    portfolio_id: str
    aggregate_id: str
    symbol: str
    security_type: str
    direction: str
    quantity: float
    average_entry_price: float
    current_price: float
    opened_at: str
    expiry: str = ""
    strike: float | None = None
    right: str = ""
    local_symbol: str = ""
    contract_id: int = 0
    currency: str = "USD"
    sector: str = "UNKNOWN"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PositionExitAssessment:
    position_id: str
    symbol: str
    action: str
    trigger: str
    allowed: bool
    urgency: str
    unrealized_pnl: float
    unrealized_return_pct: float
    holding_minutes: float
    target_price: float
    stop_price: float
    exit_quantity: float
    rejection_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PositionExitOrderIntent:
    intent_id: str
    position_id: str
    portfolio_id: str
    symbol: str
    asset_class: str
    side: str
    quantity: float
    order_type: str
    time_in_force: str
    limit_price: float | None
    expiry: str = ""
    strike: float | None = None
    right: str = ""
    local_symbol: str = ""
    contract_id: int = 0
    currency: str = "USD"
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AutomatedPositionManagementResult:
    milestone: int
    phase: int
    portfolio_id: str
    mode: str
    total_positions: int
    exit_candidates: int
    monitor_only: int
    blocked_exits: int
    submitted_exits: int
    assessments: tuple[dict[str, Any], ...]
    intents: tuple[dict[str, Any], ...]
    submissions: tuple[dict[str, Any], ...]
    status: str
    created_at: str = field(default_factory=utc_now_iso)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

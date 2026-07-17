from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class PaperPositionLot:
    lot_id: str
    fill_id: str
    quantity: float
    price: float
    commission: float
    opened_at: str
    remaining_quantity: float
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PaperPositionProfile:
    position_id: str
    session_id: str
    account_id: str
    aggregate_id: str
    symbol: str
    asset_class: str
    side: str
    quantity: float
    average_cost: float
    multiplier: int
    market_price: float
    market_value: float
    cost_basis: float
    realized_pnl: float
    unrealized_pnl: float
    total_commissions: float
    state: str = "OPEN"
    lots: tuple[PaperPositionLot, ...] = ()
    high_water_mark: float | None = None
    low_water_mark: float | None = None
    profit_target_pct: float | None = None
    stop_loss_pct: float | None = None
    trailing_stop_pct: float | None = None
    adjustment_count: int = 0
    opened_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    closed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        return self.state in {"OPEN", "PARTIALLY_CLOSED", "ADJUSTED"}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class PaperExitSignal:
    position_id: str
    action: str
    reason: str
    quantity: float
    reference_price: float
    trigger_value: float
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PaperAdjustmentProposal:
    position_id: str
    adjustment_type: str
    reason: str
    quantity: float
    target_symbol: str | None = None
    target_price: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PaperPositionDecision:
    valid: bool
    allowed: bool
    action: str
    position_id: str
    recommendation: str
    position: PaperPositionProfile | None = None
    exit_signal: PaperExitSignal | None = None
    adjustment: PaperAdjustmentProposal | None = None
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

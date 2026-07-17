from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RealTimeQuoteSnapshot:
    symbol: str
    bid: float
    ask: float
    last: float
    timestamp: str
    source: str = "UNKNOWN"
    sequence: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def midpoint(self) -> float:
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return self.last


@dataclass(frozen=True)
class RealTimePositionSnapshot:
    position_id: str
    account_id: str
    symbol: str
    underlying_symbol: str
    asset_class: str
    side: str
    quantity: float
    average_cost: float
    multiplier: int
    realized_pnl: float = 0.0
    total_commissions: float = 0.0
    sector: str | None = None
    strategy_name: str | None = None
    opened_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarkedPositionSnapshot:
    position_id: str
    account_id: str
    symbol: str
    underlying_symbol: str
    asset_class: str
    side: str
    quantity: float
    average_cost: float
    mark_price: float
    multiplier: int
    cost_basis: float
    market_value: float
    signed_exposure: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    total_commissions: float
    quote_timestamp: str
    quote_source: str
    stale_quote: bool
    sector: str | None = None
    strategy_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IntradayRiskState:
    account_id: str
    snapshot_id: str
    starting_equity: float
    peak_equity: float
    current_equity: float
    cash_balance: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    gross_exposure: float
    net_exposure: float
    long_exposure: float
    short_exposure: float
    intraday_drawdown: float
    drawdown_pct: float | None
    open_position_count: int
    stale_position_count: int
    missing_quote_count: int
    marked_positions: tuple[MarkedPositionSnapshot, ...] = ()
    by_symbol: dict[str, float] = field(default_factory=dict)
    by_underlying: dict[str, float] = field(default_factory=dict)
    by_sector: dict[str, float] = field(default_factory=dict)
    by_strategy: dict[str, float] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PositionSnapshotCheck:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PositionSnapshotDecision:
    valid: bool
    allowed: bool
    account_id: str
    snapshot_id: str
    score: float
    grade: str
    severity: str
    recommendation: str
    risk_state: IntradayRiskState | None = None
    checks: tuple[PositionSnapshotCheck, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

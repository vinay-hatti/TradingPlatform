from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PaperMarketQuote:
    symbol: str
    bid: float
    ask: float
    last: float
    timestamp: str
    bid_size: float = 0.0
    ask_size: float = 0.0
    volume: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def midpoint(self) -> float:
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return self.last


@dataclass(frozen=True)
class PaperExecutionRequest:
    execution_key: str
    session_id: str
    cycle_id: str
    order_draft: Any
    quotes: dict[str, PaperMarketQuote]
    submitted_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaperFillProfile:
    fill_id: str
    execution_key: str
    aggregate_id: str
    client_order_id: str
    leg_id: str
    symbol: str
    side: str
    quantity: float
    fill_price: float
    reference_price: float
    slippage_amount: float
    slippage_bps: float
    commission: float
    latency_ms: int
    filled_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaperExecutionRecord:
    execution_key: str
    session_id: str
    cycle_id: str
    aggregate_id: str
    client_order_id: str
    account_id: str
    order_type: str
    time_in_force: str
    status: str
    requested_quantity: float
    filled_quantity: float
    remaining_quantity: float
    average_fill_price: float | None
    gross_value: float
    commissions: float
    net_cash_flow: float
    latency_ms: int
    fills: tuple[PaperFillProfile, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PaperExecutionCheck:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PaperExecutionDecision:
    valid: bool
    allowed: bool
    execution_key: str
    aggregate_id: str
    score: float
    grade: str
    severity: str
    recommendation: str
    record: PaperExecutionRecord | None = None
    checks: tuple[PaperExecutionCheck, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

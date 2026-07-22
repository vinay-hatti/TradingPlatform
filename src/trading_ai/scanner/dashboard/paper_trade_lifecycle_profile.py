from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PaperTradeOrderLeg:
    symbol: str
    expiry: str
    strike: float
    option_type: str
    action: str
    quantity: int
    limit_price: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PaperTradeOrder:
    order_id: str
    idempotency_key: str
    strategy_id: str
    symbol: str
    direction: str
    strategy_type: str
    status: str
    order_type: str
    limit_debit: float | None
    quantity: int
    legs: tuple[PaperTradeOrderLeg, ...]
    submitted_at: str
    filled_at: str | None = None
    average_fill_debit: float | None = None
    rejection_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "idempotency_key": self.idempotency_key,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "strategy_type": self.strategy_type,
            "status": self.status,
            "order_type": self.order_type,
            "limit_debit": self.limit_debit,
            "quantity": self.quantity,
            "legs": [leg.to_dict() for leg in self.legs],
            "submitted_at": self.submitted_at,
            "filled_at": self.filled_at,
            "average_fill_debit": self.average_fill_debit,
            "rejection_reason": self.rejection_reason,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PaperPosition:
    position_id: str
    order_id: str
    strategy_id: str
    symbol: str
    direction: str
    strategy_type: str
    status: str
    quantity: int
    entry_debit: float
    max_profit: float | None
    max_loss: float | None
    breakeven: float | None
    reward_risk_ratio: float | None
    opened_at: str
    closed_at: str | None = None
    realized_pnl: float | None = None
    unrealized_pnl: float | None = None
    legs: tuple[PaperTradeOrderLeg, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_id": self.position_id,
            "order_id": self.order_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "strategy_type": self.strategy_type,
            "status": self.status,
            "quantity": self.quantity,
            "entry_debit": self.entry_debit,
            "max_profit": self.max_profit,
            "max_loss": self.max_loss,
            "breakeven": self.breakeven,
            "reward_risk_ratio": self.reward_risk_ratio,
            "opened_at": self.opened_at,
            "closed_at": self.closed_at,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "legs": [leg.to_dict() for leg in self.legs],
        }


@dataclass(frozen=True)
class PaperTradeLifecycleEvent:
    event_id: str
    order_id: str
    event_type: str
    occurred_at: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PaperTradeLifecycleRecord:
    order: PaperTradeOrder
    position: PaperPosition | None
    events: tuple[PaperTradeLifecycleEvent, ...]
    duplicate_submission: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order.to_dict(),
            "position": (
                self.position.to_dict()
                if self.position
                else None
            ),
            "events": [event.to_dict() for event in self.events],
            "duplicate_submission": self.duplicate_submission,
            "warnings": list(self.warnings),
        }

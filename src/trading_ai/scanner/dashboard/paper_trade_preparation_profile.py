from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class RefreshedStrategyLeg:
    symbol: str
    expiry: str
    strike: float
    option_type: str
    action: str
    quantity: int
    bid: float | None
    ask: float | None
    last: float | None
    mid: float | None
    spread_pct: float | None
    quote_status: str
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PaperTradePreparationPolicy:
    max_spread_pct: float = 0.20
    max_debit_drift_pct: float = 0.25
    min_reward_risk_ratio: float = 1.0
    require_complete_quotes: bool = True
    require_positive_debit: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PaperTradePreparationRecord:
    symbol: str
    direction: str
    strategy_id: str | None
    strategy_type: str | None
    decision: str
    refreshed_legs: tuple[RefreshedStrategyLeg, ...]
    original_debit: float | None
    refreshed_debit: float | None
    debit_drift_pct: float | None
    max_profit: float | None
    max_loss: float | None
    breakeven: float | None
    reward_risk_ratio: float | None
    rejection_reasons: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    paper_trade_ready: bool = False
    paper_trade_payload: dict[str, Any] | None = None
    policy: PaperTradePreparationPolicy = field(
        default_factory=PaperTradePreparationPolicy
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "strategy_id": self.strategy_id,
            "strategy_type": self.strategy_type,
            "decision": self.decision,
            "refreshed_legs": [
                leg.to_dict() for leg in self.refreshed_legs
            ],
            "original_debit": self.original_debit,
            "refreshed_debit": self.refreshed_debit,
            "debit_drift_pct": self.debit_drift_pct,
            "max_profit": self.max_profit,
            "max_loss": self.max_loss,
            "breakeven": self.breakeven,
            "reward_risk_ratio": self.reward_risk_ratio,
            "rejection_reasons": list(self.rejection_reasons),
            "warnings": list(self.warnings),
            "paper_trade_ready": self.paper_trade_ready,
            "paper_trade_payload": self.paper_trade_payload,
            "policy": self.policy.to_dict(),
        }

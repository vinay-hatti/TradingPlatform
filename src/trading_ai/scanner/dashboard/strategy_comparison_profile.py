from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class StrategyLeg:
    symbol: str
    expiry: str
    strike: float
    option_type: str
    action: str
    quantity: int = 1
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    delta: float | None = None
    implied_volatility: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyCandidate:
    strategy_id: str
    symbol: str
    expiry: str
    direction: str
    strategy_type: str
    legs: tuple[StrategyLeg, ...]
    debit: float | None = None
    credit: float | None = None
    max_profit: float | None = None
    max_loss: float | None = None
    breakeven: float | None = None
    reward_risk_ratio: float | None = None
    probability_proxy: float | None = None
    liquidity_score: float | None = None
    institutional_score: float = 0.0
    quote_quality: str = "UNKNOWN"
    warnings: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "expiry": self.expiry,
            "direction": self.direction,
            "strategy_type": self.strategy_type,
            "legs": [leg.to_dict() for leg in self.legs],
            "debit": self.debit,
            "credit": self.credit,
            "max_profit": self.max_profit,
            "max_loss": self.max_loss,
            "breakeven": self.breakeven,
            "reward_risk_ratio": self.reward_risk_ratio,
            "probability_proxy": self.probability_proxy,
            "liquidity_score": self.liquidity_score,
            "institutional_score": self.institutional_score,
            "quote_quality": self.quote_quality,
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class StrategyComparisonProfile:
    symbol: str
    direction: str
    source_contracts: int
    generated_strategies: int
    ranked_strategies: tuple[StrategyCandidate, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    comparison_policy: str = "INSTITUTIONAL_DEFAULT"

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "source_contracts": self.source_contracts,
            "generated_strategies": self.generated_strategies,
            "ranked_strategies": [
                item.to_dict() for item in self.ranked_strategies
            ],
            "warnings": list(self.warnings),
            "comparison_policy": self.comparison_policy,
        }

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class InstitutionalDecisionPolicy:
    min_institutional_score: float = 50.0
    min_liquidity_score: float = 40.0
    min_probability_proxy: float = 0.20
    min_reward_risk_ratio: float = 1.0
    allow_historical_quotes: bool = False
    allow_unpriced_strategies: bool = False
    require_defined_risk: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class InstitutionalDecisionRecord:
    symbol: str
    direction: str
    decision: str
    selected_strategy_id: str | None
    selected_strategy: dict[str, Any] | None
    approved_candidates: int
    rejected_candidates: int
    rejection_summary: dict[str, int]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    policy: InstitutionalDecisionPolicy = field(
        default_factory=InstitutionalDecisionPolicy
    )
    paper_trade_ready: bool = False
    paper_trade_payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "decision": self.decision,
            "selected_strategy_id": self.selected_strategy_id,
            "selected_strategy": self.selected_strategy,
            "approved_candidates": self.approved_candidates,
            "rejected_candidates": self.rejected_candidates,
            "rejection_summary": dict(self.rejection_summary),
            "warnings": list(self.warnings),
            "policy": self.policy.to_dict(),
            "paper_trade_ready": self.paper_trade_ready,
            "paper_trade_payload": self.paper_trade_payload,
        }

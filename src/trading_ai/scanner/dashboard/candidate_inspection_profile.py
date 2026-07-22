from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class CandidateInspectionProfile:
    symbol: str
    rank: int | None = None
    institutional_score: float | None = None
    probability_of_profit: float | None = None
    direction: str | None = None
    strategy_type: str | None = None
    sector: str | None = None
    liquidity_score: float | None = None
    open_interest: int | None = None
    volume: int | None = None
    spread_pct: float | None = None
    underlying_price: float | None = None
    expected_move: float | None = None
    market_regime: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    rejections: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)
    option_chain_command: tuple[str, ...] = field(default_factory=tuple)
    strategy_comparison_command: tuple[str, ...] = field(default_factory=tuple)
    institutional_decision_command: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        payload["rejections"] = list(self.rejections)
        payload["option_chain_command"] = list(self.option_chain_command)
        payload["strategy_comparison_command"] = list(
            self.strategy_comparison_command
        )
        payload["institutional_decision_command"] = list(
            self.institutional_decision_command
        )
        return payload

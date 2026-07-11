from dataclasses import dataclass
from typing import Any


@dataclass
class StrategyScoringContext:
    symbol: str
    strategy: str
    direction: str
    market_regime: str

    technical_score: float = 0.0
    volatility_score: float = 0.0
    expected_move_score: float = 0.0
    strategy_selection_score: float = 0.0

    strike_score: float = 0.0
    expiration_score: float = 0.0
    greeks_score: float = 0.0

    liquidity_score: float = 0.0
    execution_score: float = 0.0

    risk_reward_score: float = 0.0
    data_confidence_score: float = 0.0
    portfolio_fit_score: float = 50.0

    strategy_allowed: bool = True
    strike_allowed: bool = True
    expiration_allowed: bool = True
    greeks_allowed: bool = True
    liquidity_allowed: bool = True

    risk_profile: str = "DEFINED_RISK"
    premium_type: str = ""
    complexity: str = "STANDARD"

    strategy_candidate: Any = None
    strike_candidate: Any = None
    expiration_candidate: Any = None
    greeks_profile: Any = None
    liquidity_profile: Any = None
    expected_move_profile: Any = None
    volatility_profile: Any = None

    notes: list[str] | None = None

    def __post_init__(self):
        if self.notes is None:
            self.notes = []

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class MarketRegimeTransition:
    from_regime: str
    to_regime: str
    observation_index: int
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketRegimeProfile:
    symbol: str = "UNKNOWN"
    observation_count: int = 0

    current_regime: str = "UNKNOWN"
    previous_regime: str = "UNKNOWN"
    regime_duration: int = 0
    transition_detected: bool = False

    trend_score: float = 0.0
    volatility_score: float = 0.0
    momentum_score: float = 0.0
    drawdown_score: float = 0.0
    stability_score: float = 0.0

    annualized_volatility: float = 0.0
    short_return: float = 0.0
    medium_return: float = 0.0
    long_return: float = 0.0
    current_drawdown: float = 0.0
    maximum_drawdown: float = 0.0

    regime_score: float = 0.0
    confidence_score: float = 0.0
    regime_grade: str = "N/A"
    regime_severity: str = "UNKNOWN"

    allowed: bool = True
    valid: bool = False
    warnings: List[str] = field(default_factory=list)
    rejection_reasons: List[str] = field(default_factory=list)
    transitions: List[MarketRegimeTransition] = field(default_factory=list)
    regime_history: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def score(self) -> float:
        return self.regime_score

    @property
    def grade(self) -> str:
        return self.regime_grade

    @property
    def severity(self) -> str:
        return self.regime_severity

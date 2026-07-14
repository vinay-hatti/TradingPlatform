from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class MarketRegimeTransitionProbability:
    from_regime: str
    to_regime: str
    transition_count: int
    probability: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketRegimeHorizonForecast:
    horizon: int
    most_likely_regime: str
    probability: float
    regime_probabilities: Dict[str, float] = field(default_factory=dict)


@dataclass
class MarketRegimeForecastProfile:
    symbol: str = "UNKNOWN"
    history_observation_count: int = 0
    transition_count: int = 0
    state_count: int = 0

    current_regime: str = "UNKNOWN"
    forecast_regime: str = "UNKNOWN"
    forecast_probability: float = 0.0
    persistence_probability: float = 0.0
    transition_probability: float = 0.0
    expected_remaining_duration: float = 0.0
    current_regime_duration: int = 0

    next_regime_probabilities: Dict[str, float] = field(default_factory=dict)
    transition_probabilities: List[MarketRegimeTransitionProbability] = field(
        default_factory=list
    )
    horizon_forecasts: List[MarketRegimeHorizonForecast] = field(
        default_factory=list
    )

    transition_entropy: float = 0.0
    persistence_score: float = 0.0
    forecast_confidence_score: float = 0.0
    forecast_score: float = 0.0
    forecast_grade: str = "N/A"
    forecast_severity: str = "UNKNOWN"

    allowed: bool = True
    valid: bool = False
    warnings: List[str] = field(default_factory=list)
    rejection_reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def score(self) -> float:
        return self.forecast_score

    @property
    def grade(self) -> str:
        return self.forecast_grade

    @property
    def severity(self) -> str:
        return self.forecast_severity

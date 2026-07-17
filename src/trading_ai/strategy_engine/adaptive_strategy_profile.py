from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StrategyPerformanceProfile:
    strategy: str
    observation_count: int
    win_rate: float
    average_return: float
    profit_factor: float
    maximum_drawdown_pct: float
    sharpe_ratio: float = 0.0
    calibration_score: float = 50.0
    execution_score: float = 50.0
    context_observation_count: int = 0
    context_win_rate: float | None = None
    context_average_return: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdaptiveStrategyCandidateProfile:
    symbol: str
    strategy: str
    direction: str
    market_regime: str
    volatility_regime: str
    original_score: float
    prior_score: float
    performance_score: float
    regime_score: float
    calibration_score: float
    execution_score: float
    adaptive_adjustment: float
    adaptive_score: float
    confidence_score: float
    observation_count: int
    context_observation_count: int
    allowed: bool
    grade: str
    severity: str
    recommendation: str
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdaptiveStrategySelectionProfile:
    symbol: str
    valid: bool
    allowed: bool
    selected_strategy: str | None
    selected_score: float
    selection_confidence_score: float
    grade: str
    severity: str
    recommendation: str
    candidates: tuple[AdaptiveStrategyCandidateProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

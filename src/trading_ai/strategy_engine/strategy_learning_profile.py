from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class StrategyOutcomeRecord:
    strategy: str
    outcome_date: date
    realized_return: float
    pnl: float = 0.0
    won: bool = False
    symbol: str = ""
    direction: str = "NEUTRAL"
    market_regime: str = "UNKNOWN"
    volatility_regime: str = "UNKNOWN"
    calibration_score: float = 50.0
    execution_score: float = 50.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyLearningSegmentProfile:
    strategy: str
    segment_key: str
    segment_value: str
    observation_count: int
    effective_sample_size: float
    weighted_win_rate: float
    weighted_average_return: float
    weighted_return_volatility: float
    profit_factor: float
    maximum_drawdown_pct: float
    sharpe_ratio: float
    stability_score: float
    recency_score: float
    performance_score: float
    valid: bool
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyLearningProfile:
    strategy: str
    valid: bool
    allowed: bool
    observation_count: int
    effective_sample_size: float
    weighted_win_rate: float
    weighted_average_return: float
    weighted_return_volatility: float
    profit_factor: float
    maximum_drawdown_pct: float
    sharpe_ratio: float
    calibration_score: float
    execution_score: float
    stability_score: float
    recency_score: float
    performance_score: float
    confidence_score: float
    grade: str
    severity: str
    segments: tuple[StrategyLearningSegmentProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DynamicStrategyWeightProfile:
    strategy: str
    valid: bool
    allowed: bool
    prior_weight: float
    performance_component: float
    stability_component: float
    recency_component: float
    raw_weight: float
    normalized_weight: float
    confidence_score: float
    grade: str
    severity: str
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyWeightingProfile:
    valid: bool
    allowed: bool
    strategy_count: int
    total_weight: float
    weights: tuple[DynamicStrategyWeightProfile, ...]
    concentration_score: float
    effective_strategy_count: float
    grade: str
    severity: str
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

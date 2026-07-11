from dataclasses import dataclass, field

from trading_ai.strategy_engine.strategy_score_breakdown import (
    StrategyScoreBreakdown,
)


@dataclass
class StrategyScoringResult:
    symbol: str
    strategy: str
    direction: str
    market_regime: str

    composite_score: float
    raw_composite_score: float
    total_penalty: float

    grade: str
    confidence_label: str
    readiness: str

    allowed: bool
    rejection_reasons: list[str]

    strengths: list[str]
    weaknesses: list[str]
    warnings: list[str]

    primary_reason: str
    recommendation: str

    breakdown: StrategyScoreBreakdown

    metadata: dict = field(default_factory=dict)

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TechnicalAnalysisProfile:
    trend_score: float
    momentum_score: float
    regime_score: float
    technical_score: float
    signal: str
    regime: str
    positive_factors: tuple[str, ...] = ()
    negative_factors: tuple[str, ...] = ()


@dataclass(frozen=True)
class LiquidityAnalysisProfile:
    average_volume: int
    option_volume: int
    open_interest: int
    spread_pct: float
    liquidity_score: float
    market_quality: str
    positive_factors: tuple[str, ...] = ()
    negative_factors: tuple[str, ...] = ()


@dataclass(frozen=True)
class VolatilityAnalysisProfile:
    iv_rank: float
    iv_percentile: float
    atr_pct: float
    volatility_score: float
    volatility_state: str
    positive_factors: tuple[str, ...] = ()
    negative_factors: tuple[str, ...] = ()


@dataclass(frozen=True)
class InstitutionalAnalysisProfile:
    available: bool
    strategy: str
    action: str
    readiness: str
    allowed: bool
    selected: bool
    probability_of_profit: float
    calibrated_probability: float
    institutional_score: float
    decision_confidence: float
    tail_risk_grade: str
    recommended_position_size_pct: float
    positive_factors: tuple[str, ...] = ()
    negative_factors: tuple[str, ...] = ()


@dataclass(frozen=True)
class RiskAnalysisProfile:
    risk_score: float
    expected_return: float
    reward_risk_ratio: float
    stop_loss_pct: float
    take_profit_pct: float
    risk_grade: str
    positive_factors: tuple[str, ...] = ()
    negative_factors: tuple[str, ...] = ()


@dataclass(frozen=True)
class DecisionExplanationProfile:
    recommendation: str
    readiness: str
    confidence: float
    summary: str
    positive_contributors: tuple[str, ...] = ()
    negative_contributors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_factors: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateAnalysisProfile:
    symbol: str
    price: float
    signal: str
    regime: str
    composite_score: float
    trade_readiness_score: float
    technical: TechnicalAnalysisProfile
    liquidity: LiquidityAnalysisProfile
    volatility: VolatilityAnalysisProfile
    institutional: InstitutionalAnalysisProfile
    risk: RiskAnalysisProfile
    explanation: DecisionExplanationProfile
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

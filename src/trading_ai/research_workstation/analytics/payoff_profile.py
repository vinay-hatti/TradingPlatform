from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .greeks_profile import GreeksExposureProfile
from .risk_visualization_profile import (
    RiskClassificationProfile,
    VisualizationSeriesProfile,
)


@dataclass(frozen=True)
class StrategyLegProfile:
    symbol: str
    option_type: str
    side: str
    strike: float
    premium: float
    quantity: int = 1
    multiplier: int = 100
    expiration: str = ""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0


@dataclass(frozen=True)
class PayoffPointProfile:
    underlying_price: float
    profit_loss: float


@dataclass(frozen=True)
class PayoffAnalysisProfile:
    strategy_name: str
    underlying_price: float
    net_credit_debit: float
    maximum_profit: float | None
    maximum_loss: float | None
    breakeven_points: tuple[float, ...]
    return_on_risk: float
    reward_risk_ratio: float
    probability_adjusted_expected_payoff: float
    risk_adjusted_expected_return: float
    payoff_points: tuple[PayoffPointProfile, ...]
    greeks: GreeksExposureProfile
    risk_classification: RiskClassificationProfile
    visualization_series: tuple[VisualizationSeriesProfile, ...]
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

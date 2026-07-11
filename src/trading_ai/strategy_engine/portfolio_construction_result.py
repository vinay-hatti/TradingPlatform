from dataclasses import dataclass, field

from trading_ai.strategy_engine.portfolio_exposure import (
    PortfolioExposure,
)
from trading_ai.strategy_engine.portfolio_position import (
    PortfolioPosition,
)


@dataclass
class PortfolioRejection:
    symbol: str
    strategy: str
    ranking_score: float

    reasons: list[str]
    warnings: list[str] = field(default_factory=list)


@dataclass
class PortfolioConstructionResult:
    positions: list[PortfolioPosition]
    rejected: list[PortfolioRejection]

    exposure: PortfolioExposure

    valid: bool
    readiness: str

    portfolio_score: float
    diversification_score: float
    risk_score: float
    capital_efficiency_score: float

    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    metadata: dict = field(default_factory=dict)

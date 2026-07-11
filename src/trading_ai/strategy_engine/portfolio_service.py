from trading_ai.strategy_engine.portfolio_constructor import (
    PortfolioConstructor,
)
from trading_ai.strategy_engine.portfolio_risk_limits import (
    PortfolioRiskLimits,
)


class PortfolioService:
    """
    Unified Phase 11 entry point.
    """

    def __init__(
        self,
        limits: PortfolioRiskLimits | None = None,
    ):
        self.limits = (
            limits
            or PortfolioRiskLimits()
        )

        self.constructor = PortfolioConstructor(
            limits=self.limits
        )

    def construct(
        self,
        ranked_opportunities,
    ):
        return self.constructor.construct(
            ranked_opportunities
        )

    def exposure(
        self,
        positions,
    ):
        return self.constructor.calculate_exposure(
            positions
        )

from trading_ai.strategy_engine.distribution_risk_engine import (
    DistributionRiskEngine,
)
from trading_ai.strategy_engine.distribution_risk_policy import (
    DistributionRiskPolicy,
)
from trading_ai.strategy_engine.portfolio_tail_risk_engine import (
    PortfolioTailRiskEngine,
)


class DistributionRiskService:
    """
    Unified Phase 3 risk-analysis service.
    """

    def __init__(
        self,
        policy: DistributionRiskPolicy | None = None,
        engine=None,
        portfolio_engine=None,
    ):
        self.policy = (
            policy
            or DistributionRiskPolicy()
        )

        self.engine = (
            engine
            or DistributionRiskEngine(
                policy=self.policy
            )
        )

        self.portfolio_engine = (
            portfolio_engine
            or PortfolioTailRiskEngine(
                policy=self.policy,
                distribution_engine=(
                    self.engine
                ),
            )
        )

    def analyze_strategy(
        self,
        pnl_values,
        capital_required,
        symbol="",
        strategy="",
        monte_carlo_pnl_values=None,
        initial_capital=None,
    ):
        return self.engine.analyze(
            pnl_values=pnl_values,
            capital_required=(
                capital_required
            ),
            symbol=symbol,
            strategy=strategy,
            monte_carlo_pnl_values=(
                monte_carlo_pnl_values
            ),
            initial_capital=(
                initial_capital
            ),
        )

    def analyze_portfolio(
        self,
        pnl_matrix,
        position_metadata,
        initial_capital,
        weights=None,
    ):
        return self.portfolio_engine.analyze(
            pnl_matrix=pnl_matrix,
            position_metadata=(
                position_metadata
            ),
            initial_capital=(
                initial_capital
            ),
            weights=weights,
        )

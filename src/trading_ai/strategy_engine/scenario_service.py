from trading_ai.strategy_engine.portfolio_scenario_engine import (
    PortfolioScenarioEngine,
)
from trading_ai.strategy_engine.scenario_engine import (
    ScenarioEngine,
)
from trading_ai.strategy_engine.scenario_policy import (
    ScenarioPolicy,
)


class ScenarioService:
    """
    Unified Phase 2 scenario-analysis service.
    """

    def __init__(
        self,
        policy: ScenarioPolicy | None = None,
        scenario_engine=None,
        portfolio_scenario_engine=None,
    ):
        self.policy = (
            policy
            or ScenarioPolicy()
        )

        self.scenario_engine = (
            scenario_engine
            or ScenarioEngine(
                policy=self.policy
            )
        )

        self.portfolio_scenario_engine = (
            portfolio_scenario_engine
            or PortfolioScenarioEngine(
                scenario_engine=(
                    self.scenario_engine
                ),
                policy=self.policy,
            )
        )

    def analyze_strategy(
        self,
        structure,
        volatility,
        days_to_expiry,
        capital_required=None,
        maximum_loss=None,
        scenarios=None,
    ):
        return self.scenario_engine.analyze(
            structure=structure,
            volatility=volatility,
            days_to_expiry=days_to_expiry,
            capital_required=capital_required,
            maximum_loss=maximum_loss,
            scenarios=scenarios,
        )

    def analyze_portfolio(
        self,
        positions,
        initial_capital,
        volatility_by_symbol,
        dte_by_symbol=None,
    ):
        return (
            self.portfolio_scenario_engine
            .analyze(
                positions=positions,
                initial_capital=(
                    initial_capital
                ),
                volatility_by_symbol=(
                    volatility_by_symbol
                ),
                dte_by_symbol=(
                    dte_by_symbol
                ),
            )
        )

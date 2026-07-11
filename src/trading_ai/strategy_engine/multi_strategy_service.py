from trading_ai.strategy_engine.multi_strategy_builder import (
    MultiStrategyBuilder,
)
from trading_ai.strategy_engine.multi_strategy_validator import (
    MultiStrategyValidator,
)
from trading_ai.strategy_engine.strategy_payoff_engine import (
    StrategyPayoffEngine,
)


class MultiStrategyService:
    """
    Unified Phase 10 service.
    """

    def __init__(
        self,
        builder=None,
        validator=None,
        payoff_engine=None,
    ):
        self.builder = (
            builder
            or MultiStrategyBuilder()
        )

        self.validator = (
            validator
            or MultiStrategyValidator()
        )

        self.payoff_engine = (
            payoff_engine
            or StrategyPayoffEngine()
        )

    def analyze(
        self,
        structure,
        estimated_leg_values=None,
        expected_profit=None,
    ):
        return self.payoff_engine.analyze(
            structure=structure,
            estimated_leg_values=(
                estimated_leg_values
            ),
            expected_profit=expected_profit,
        )

    def build_and_analyze(
        self,
        symbol,
        strategy,
        underlying_price,
        legs,
        contracts=1,
        estimated_leg_values=None,
        expected_profit=None,
        metadata=None,
    ):
        structure = self.builder.build(
            symbol=symbol,
            strategy=strategy,
            underlying_price=underlying_price,
            legs=legs,
            contracts=contracts,
            metadata=metadata,
        )

        return (
            structure,
            self.analyze(
                structure=structure,
                estimated_leg_values=(
                    estimated_leg_values
                ),
                expected_profit=expected_profit,
            ),
        )

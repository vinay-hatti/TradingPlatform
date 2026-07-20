from __future__ import annotations

from typing import Iterable

from trading_ai.research_workstation.analysis.option_chain_explorer_profile import (
    OptionContractAnalysisProfile,
)

from .payoff_engine import PayoffAnalysisEngine
from .payoff_profile import (
    PayoffAnalysisProfile,
    StrategyLegProfile,
)


class PayoffAnalysisService:
    def __init__(
        self,
        engine: PayoffAnalysisEngine | None = None,
    ):
        self.engine = engine or PayoffAnalysisEngine()

    @staticmethod
    def leg_from_contract(
        contract: OptionContractAnalysisProfile,
        *,
        side: str,
        quantity: int = 1,
        multiplier: int = 100,
    ) -> StrategyLegProfile:
        return StrategyLegProfile(
            symbol=contract.symbol,
            option_type=contract.option_type,
            side=side,
            strike=contract.strike,
            premium=contract.mark,
            quantity=quantity,
            multiplier=multiplier,
            expiration=(
                contract.expiration.isoformat()
                if contract.expiration
                else ""
            ),
            delta=contract.delta,
            gamma=contract.gamma,
            theta=contract.theta,
            vega=contract.vega,
            rho=0.0,
        )

    def analyze(
        self,
        *,
        strategy_name: str,
        underlying_price: float,
        legs: Iterable[StrategyLegProfile],
        minimum_price: float | None = None,
        maximum_price: float | None = None,
        steps: int = 121,
    ) -> PayoffAnalysisProfile:
        return self.engine.analyze(
            strategy_name=strategy_name,
            underlying_price=underlying_price,
            legs=legs,
            minimum_price=minimum_price,
            maximum_price=maximum_price,
            steps=steps,
        )

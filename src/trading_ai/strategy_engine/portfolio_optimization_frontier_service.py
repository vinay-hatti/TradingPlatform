from __future__ import annotations

from typing import Any, Iterable

from trading_ai.strategy_engine.portfolio_optimization_frontier_engine import (
    PortfolioOptimizationFrontierEngine,
)
from trading_ai.strategy_engine.portfolio_optimization_frontier_policy import (
    PortfolioOptimizationFrontierPolicy,
)
from trading_ai.strategy_engine.portfolio_optimization_policy import (
    PortfolioOptimizationPolicy,
)


class PortfolioOptimizationFrontierService:
    def __init__(
        self,
        base_policy: PortfolioOptimizationPolicy | None = None,
        frontier_policy: PortfolioOptimizationFrontierPolicy | None = None,
        engine: PortfolioOptimizationFrontierEngine | None = None,
    ) -> None:
        self.base_policy = base_policy or PortfolioOptimizationPolicy()
        self.frontier_policy = frontier_policy or PortfolioOptimizationFrontierPolicy()
        self.engine = engine or PortfolioOptimizationFrontierEngine(
            base_policy=self.base_policy,
            frontier_policy=self.frontier_policy,
        )

    def analyze(
        self,
        candidates: Iterable[Any],
        initial_capital: float,
    ):
        return self.engine.analyze(candidates, initial_capital)

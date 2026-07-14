from typing import Any, Mapping, Sequence

from trading_ai.strategy_engine.market_breadth_engine import MarketBreadthEngine
from trading_ai.strategy_engine.market_breadth_policy import MarketBreadthPolicy
from trading_ai.strategy_engine.market_breadth_profile import MarketBreadthProfile


class MarketBreadthService:
    def __init__(self, policy: MarketBreadthPolicy | None = None, engine: MarketBreadthEngine | None = None):
        self.policy = policy or MarketBreadthPolicy()
        self.engine = engine or MarketBreadthEngine(self.policy)

    def analyze_portfolio(
        self,
        regime_profiles: Mapping[str, Any] | Sequence[Any],
        weights: Mapping[str, float] | Sequence[float] | None = None,
    ) -> MarketBreadthProfile:
        return self.engine.analyze(regime_profiles, weights=weights)

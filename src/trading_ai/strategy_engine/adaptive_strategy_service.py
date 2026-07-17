from typing import Any, Iterable

from trading_ai.strategy_engine.adaptive_strategy_engine import AdaptiveStrategyEngine
from trading_ai.strategy_engine.adaptive_strategy_policy import AdaptiveStrategyPolicy


class AdaptiveStrategyService:
    """Service facade preserving the existing selector as the prior generator."""

    def __init__(self, policy: AdaptiveStrategyPolicy | None = None, engine: AdaptiveStrategyEngine | None = None):
        self.engine = engine or AdaptiveStrategyEngine(policy=policy)

    def evaluate(self, symbol: str, candidates: Iterable[Any], performance_profiles: Any = None):
        return self.engine.select(symbol=symbol, candidates=candidates, performance_profiles=performance_profiles)

    def select_from_rule_based_selector(
        self,
        selector: Any,
        symbol: str,
        direction: str,
        market_regime: str,
        volatility_profile: Any,
        expected_move_profile: Any = None,
        performance_profiles: Any = None,
    ):
        candidates = selector.select(
            symbol=symbol,
            direction=direction,
            market_regime=market_regime,
            volatility_profile=volatility_profile,
            expected_move_profile=expected_move_profile,
        )
        return self.evaluate(symbol, candidates, performance_profiles)

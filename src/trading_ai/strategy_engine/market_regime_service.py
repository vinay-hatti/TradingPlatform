from typing import Any, Dict

from trading_ai.strategy_engine.market_regime_engine import (
    MarketRegimeEngine,
)
from trading_ai.strategy_engine.market_regime_policy import (
    MarketRegimePolicy,
)
from trading_ai.strategy_engine.market_regime_profile import (
    MarketRegimeProfile,
)


class MarketRegimeService:
    def __init__(
        self,
        policy: MarketRegimePolicy | None = None,
        engine: MarketRegimeEngine | None = None,
    ):
        self.policy = policy or MarketRegimePolicy()
        self.engine = engine or MarketRegimeEngine(self.policy)

    def analyze(
        self,
        prices: Any,
        symbol: str = "UNKNOWN",
    ) -> MarketRegimeProfile:
        return self.engine.analyze(prices=prices, symbol=symbol)

    def analyze_many(
        self,
        prices_by_symbol: Dict[str, Any],
    ) -> Dict[str, MarketRegimeProfile]:
        return {
            symbol: self.analyze(prices=prices, symbol=symbol)
            for symbol, prices in prices_by_symbol.items()
        }

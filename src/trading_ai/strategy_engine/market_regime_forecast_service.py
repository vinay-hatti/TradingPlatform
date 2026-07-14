from typing import Dict, Iterable, Sequence

from trading_ai.strategy_engine.market_regime_forecast_engine import (
    MarketRegimeForecastEngine,
)
from trading_ai.strategy_engine.market_regime_forecast_policy import (
    MarketRegimeForecastPolicy,
)
from trading_ai.strategy_engine.market_regime_forecast_profile import (
    MarketRegimeForecastProfile,
)
from trading_ai.strategy_engine.market_regime_profile import MarketRegimeProfile


class MarketRegimeForecastService:
    def __init__(
        self,
        policy: MarketRegimeForecastPolicy | None = None,
        engine: MarketRegimeForecastEngine | None = None,
    ):
        self.policy = policy or MarketRegimeForecastPolicy()
        self.engine = engine or MarketRegimeForecastEngine(self.policy)

    def forecast_profile(
        self,
        regime_profile: MarketRegimeProfile,
    ) -> MarketRegimeForecastProfile:
        return self.engine.forecast_profile(regime_profile)

    def forecast(
        self,
        regime_history: Sequence[str] | Iterable[str],
        symbol: str = "UNKNOWN",
    ) -> MarketRegimeForecastProfile:
        return self.engine.forecast(regime_history, symbol=symbol)

    def forecast_many(
        self,
        profiles_by_symbol: Dict[str, MarketRegimeProfile],
    ) -> Dict[str, MarketRegimeForecastProfile]:
        return {
            symbol: self.forecast_profile(profile)
            for symbol, profile in profiles_by_symbol.items()
        }

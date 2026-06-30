from polygon import RESTClient
from trading_ai.config import settings
from trading_ai.market.dto import MarketBar
import pandas as pd

class PolygonProvider:

    def __init__(self):
        self.client = RESTClient(settings.polygon_api_key)
        self.options_provider = None
        self._analytics_cache = {}

    def get_analytics(self, symbol):
        
        if symbol in self._analytics_cache:
            return self._analytics_cache[symbol]

        if self.options_provider is None:
            analytics = {
                "iv_rank": 0.5,
                "skew": {"skew": 0.0},
            }
        else:
            analytics = self.options_provider.get_analytics(symbol)
      
        self._analytics_cache[symbol] = analytics
        return analytics

#    def __init__(self):
#        self.client = RESTClient(settings.polygon_api_key)
#        self.options_provider = None
#
#    def get_analytics(self, symbol: str):
#
#        if self.options_provider is not None:
#            return self.options_provider.get_analytics(symbol)
#
#        return {
#            "iv_rank": 0.5,
#            "skew": {"skew": 0.0},
#        }

    def fetch_history(self, symbol: str, start: str, end: str):
        
        aggs = self.client.get_aggs(
            ticker=symbol,
            multiplier=1,
            timespan="day",
            from_=start,
            to=end,
        )

        bars = []

        for a in aggs:
            bars.append(
                MarketBar(
                    symbol=symbol,
                    time=a.timestamp,
                    open=float(a.open),
                    high=float(a.high),
                    low=float(a.low),
                    close=float(a.close),
                    volume=float(a.volume),
                )
            )

        return bars

    def to_dataframe(self, bars):

        df = pd.DataFrame([b.__dict__ for b in bars])

        df = df.sort_values("time").reset_index(drop=True)

        return df

import yfinance as yf
import pandas as pd
from .provider import MarketDataProvider


class YahooProvider(MarketDataProvider):

    def history(self, symbol: str, period="1y", interval="1d") -> pd.DataFrame:
        df = yf.download(symbol, period=period, interval=interval, auto_adjust=True)
        df.reset_index(inplace=True)
        return df

    def quote(self, symbol: str) -> dict:
        t = yf.Ticker(symbol)
        return t.fast_info

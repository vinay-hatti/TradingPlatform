import pandas as pd
from typing import List
from trading_ai.domain.market import MarketBar


def bars_to_dataframe(bars: List[MarketBar]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "symbol": b.symbol,
            "time": b.time,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        }
        for b in bars
    ])

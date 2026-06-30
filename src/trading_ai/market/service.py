from pathlib import Path
import pickle
import pandas as pd

from trading_ai.market.providers.polygon import PolygonProvider


class MarketService:

    def __init__(self):
        self.provider = PolygonProvider()
        self.cache_dir = Path(".cache/market")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_file(self, symbol, start, end):
        return self.cache_dir / f"{symbol}_{start}_{end}.pkl"

    def _load_cached_df(self, symbol, start, end):

        exact_file = self._cache_file(symbol, start, end)

        if exact_file.exists():
            with open(exact_file, "rb") as f:
                return pickle.load(f)

        # Try larger cached ranges
        for file in self.cache_dir.glob(f"{symbol}_*.pkl"):
            try:
                with open(file, "rb") as f:
                    df = pickle.load(f)

                if "time" not in df.columns:
                    continue

                temp = df.copy()
                temp["date"] = pd.to_datetime(temp["time"], unit="ms").dt.date.astype(str)

                cached_min = temp["date"].min()
                cached_max = temp["date"].max()

                if cached_min <= start and cached_max >= end:
                    return temp[
                        (temp["date"] >= start)
                        & (temp["date"] <= end)
                    ].drop(columns=["date"]).reset_index(drop=True)

            except Exception:
                continue

        return None

    def get_history(self, symbol, start, end):

        symbol = symbol.upper()
        start = str(start)
        end = str(end)

        cached = self._load_cached_df(symbol, start, end)

        if cached is not None:
            return cached

        bars = self.provider.fetch_history(symbol, start, end)

        df = pd.DataFrame([{
            "symbol": b.symbol,
            "time": b.time,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
        } for b in bars])

        cache_file = self._cache_file(symbol, start, end)

        with open(cache_file, "wb") as f:
            pickle.dump(df, f)

        return df

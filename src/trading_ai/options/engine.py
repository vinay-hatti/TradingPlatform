import pickle
import time
from pathlib import Path
from trading_ai.options.quality import OptionQualityScorer
from trading_ai.options.selector import OptionsSelector
from trading_ai.options.ranker import OptionRanker


class OptionsEngine:

    def __init__(self, provider):
        self.provider = provider
        self.selector = OptionsSelector()
        self._chain_cache = {}

        self.cache_dir = Path(".cache/options")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.quality = OptionQualityScorer()
        self.ranker = OptionRanker()

    def _cache_file(self, symbol):
        return self.cache_dir / f"{symbol}_chain.pkl"

    def _load_chain(self, symbol):

        if symbol in self._chain_cache:
            return self._chain_cache[symbol]

        cache_file = self._cache_file(symbol)

        if cache_file.exists():
            print(f"Loading cached option chain for {symbol}")
            with open(cache_file, "rb") as f:
                chain = pickle.load(f)

            self._chain_cache[symbol] = chain
            return chain

        print(f"Downloading option chain for {symbol}")

        t0 = time.perf_counter()
        chain = self.provider.get_chain(symbol)
        elapsed = time.perf_counter() - t0

        print(f"Chain download took {elapsed:.2f}s")

        with open(cache_file, "wb") as f:
            pickle.dump(chain, f)

        self._chain_cache[symbol] = chain
        return chain

    def rank_contracts(self, symbol, ctx, analytics, strategy=None, limit=10):

        chain = self._load_chain(symbol)

        if strategy == "LONG_CALL":
            signal = "CALL"
        elif strategy == "LONG_PUT":
            signal = "PUT"
        else:
            signal = "CALL" if ctx.call_score >= ctx.put_score else "PUT"

        candidates = [
            c for c in chain
            if c.option_type == signal
            and c.implied_volatility > 0
            and c.open_interest > 10
            and abs(c.delta) > 0.15
        ]

        underlying_price = float(
            getattr(ctx, "close", 0.0)
            or getattr(ctx, "current_price", 0.0)
            or getattr(ctx, "underlying_price", 0.0)
            or 0.0
        )

        if not candidates:
            return []

        return self.ranker.rank(
            candidates,
            signal=signal,
            limit=limit,
            spot=underlying_price,
        )

    def select_contract(self, symbol, ctx, analytics, strategy=None):

        chain = self._load_chain(symbol)

        if strategy == "LONG_CALL":
            signal = "CALL"
        elif strategy == "LONG_PUT":
            signal = "PUT"
        else:
            signal = "CALL" if ctx.call_score >= ctx.put_score else "PUT"

        skew = analytics.get("skew", {}).get("skew", 0.0)

        candidates = [
            c for c in chain
            if c.option_type == signal
            and c.implied_volatility > 0
            and c.open_interest > 10
            and abs(c.delta) > 0.15
        ]

        underlying_price = float(
            getattr(ctx, "close", 0.0)
            or getattr(ctx, "stock_price", 0.0)
            or getattr(ctx, "underlying_price", 0.0)
        )

        if not candidates:
            return None

        ranked = self.ranker.rank(
            candidates,
            signal=signal,
            limit=10,
            spot=underlying_price,
        )

        if not ranked:
            return None

        return ranked[0].option


from __future__ import annotations

from pathlib import Path
import pickle
import tempfile

import pandas as pd

from trading_ai.market.service import (
    MarketDataNotCachedError,
    MarketService,
)


class NoNetworkProvider:
    def fetch_history(self, *args, **kwargs):
        raise AssertionError("network provider must not be called")


def frame_ending_before_requested_end() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": ["AMZN", "AMZN", "AMZN"],
            "time": [
                1752710400000,  # 2025-07-17 UTC
                1784159999000,  # 2026-07-15 UTC-ish
                1784246399000,  # 2026-07-16 UTC-ish
            ],
            "open": [220.0, 230.0, 231.0],
            "high": [222.0, 232.0, 233.0],
            "low": [218.0, 228.0, 229.0],
            "close": [221.0, 231.0, 232.0],
            "volume": [1000.0, 1100.0, 1200.0],
        }
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        service = MarketService(
            provider=NoNetworkProvider(),
            cache_dir=temp_dir,
        )

        exact = service._cache_file(
            "AMZN",
            "2025-07-17",
            "2026-07-17",
        )
        with exact.open("wb") as handle:
            pickle.dump(
                frame_ending_before_requested_end(),
                handle,
            )

        loaded = service.get_history(
            "AMZN",
            "2025-07-17",
            "2026-07-17",
            cache_only=True,
        )
        assert not loaded.empty
        assert len(loaded) == 3

        empty = service._cache_file(
            "META",
            "2025-07-17",
            "2026-07-17",
        )
        with empty.open("wb") as handle:
            pickle.dump(pd.DataFrame(), handle)

        try:
            service.get_history(
                "META",
                "2025-07-17",
                "2026-07-17",
                cache_only=True,
            )
        except MarketDataNotCachedError:
            pass
        else:
            raise AssertionError(
                "An empty cache file must not satisfy cache-only mode"
            )

    print("All market-cache requested-range assertions passed.")


if __name__ == "__main__":
    main()

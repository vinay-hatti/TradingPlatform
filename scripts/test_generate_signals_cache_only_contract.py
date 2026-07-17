from __future__ import annotations

import argparse
import pickle
import tempfile
from pathlib import Path

import pandas as pd

from trading_ai.backtest.datasource import HistoricalDataSource
from trading_ai.market.service import MarketDataNotCachedError, MarketService
from trading_ai.options.pricing_service import OptionPricingService


class NoNetworkProvider:
    def fetch_history(self, *args, **kwargs):
        raise AssertionError("network provider must not be called")


def main() -> None:
    greeks = OptionPricingService().greeks(
        signal="CALL",
        spot=100.0,
        strike=100.0,
        hv20=0.25,
        dte=45,
    )
    assert greeks["dte"] == 45

    with tempfile.TemporaryDirectory() as temp:
        service = MarketService(
            provider=NoNetworkProvider(),
            cache_dir=Path(temp),
        )
        source = HistoricalDataSource(service, cache_only=True)

        try:
            source.get_price_history(
                "AMZN",
                "2025-07-17",
                "2026-07-17",
            )
        except MarketDataNotCachedError:
            pass
        else:
            raise AssertionError("cache-only miss did not raise")

        frame = pd.DataFrame(
            {
                "symbol": ["AMZN", "AMZN"],
                "time": [1752710400000, 1784246400000],
                "open": [200.0, 210.0],
                "high": [201.0, 211.0],
                "low": [199.0, 209.0],
                "close": [200.5, 210.5],
                "volume": [1000.0, 1200.0],
            }
        )
        cache = service._cache_file(
            "AMZN",
            "2025-07-17",
            "2026-07-17",
        )
        with cache.open("wb") as handle:
            pickle.dump(frame, handle)

        cached = source.get_price_history(
            "AMZN",
            "2025-07-17",
            "2026-07-17",
        )
        assert len(cached) == 2

    # Validate symbol normalization without importing runtime-heavy scanner deps.
    scan_text = Path("scripts/run_daily_scan.py").read_text()
    assert '.replace("_", ".")' in scan_text
    assert "cache_only=not args.allow_network" in scan_text
    assert '"--allow-network"' in scan_text

    print("All generate-signals cache-only and DTE assertions passed.")


if __name__ == "__main__":
    main()

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from trading_ai.research_workstation.scanner import (
    HistoricalFeatureAdapter,
    MarketBarProfile,
    MarketCandidateFactory,
    MarketScanRequestProfile,
    MarketScannerInputService,
    MarketScannerService,
    MarketUniverseProfile,
    ScannerFilterProfile,
    StaticMarketUniverseProvider,
)


class FakeMarketDataAdapter:
    def __init__(self, data):
        self.data = data

    def load_bars(self, *, symbols, start=None, end=None):
        return {symbol: tuple(self.data.get(symbol, ())) for symbol in symbols}


def make_bars(symbol: str, *, rising: bool, count: int = 30):
    start = date(2026, 1, 1)
    bars = []
    for index in range(count):
        close = 100.0 + index if rising else 100.0 - index
        bars.append(
            MarketBarProfile(
                symbol=symbol,
                trading_date=start + timedelta(days=index),
                open=close - 0.5,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=2_000_000 + index * 10_000,
            )
        )
    return bars


def main() -> None:
    universe_provider = StaticMarketUniverseProvider(
        (
            MarketUniverseProfile(
                name="test",
                symbols=("aaa", "BBB", "AAA", "CCC"),
            ),
        )
    )
    universe = universe_provider.load("test")
    assert universe.symbols == ("AAA", "BBB", "CCC")

    adapter = FakeMarketDataAdapter(
        {
            "AAA": make_bars("AAA", rising=True),
            "BBB": make_bars("BBB", rising=False),
            "CCC": make_bars("CCC", rising=True, count=5),
        }
    )

    service = MarketScannerInputService(
        universe_provider=universe_provider,
        market_data_adapter=adapter,
        feature_adapter=HistoricalFeatureAdapter(),
        candidate_factory=MarketCandidateFactory(),
    )

    result = service.build_candidates(universe_name="test")
    assert result.requested_symbols == ("AAA", "BBB", "CCC")
    assert len(result.candidates) == 2
    assert result.skipped_symbols == ("CCC",)

    by_symbol = {candidate.symbol: candidate for candidate in result.candidates}
    assert by_symbol["AAA"].signal == "CALL"
    assert by_symbol["AAA"].regime == "TREND_UP"
    assert by_symbol["BBB"].signal == "PUT"
    assert by_symbol["BBB"].regime == "TREND_DOWN"
    assert by_symbol["AAA"].average_volume > 2_000_000
    assert by_symbol["AAA"].atr_pct > 0

    request = MarketScanRequestProfile(
        scan_id="step2-test",
        universe=result.requested_symbols,
        filters=ScannerFilterProfile(
            min_price=10.0,
            min_average_volume=1_000_000,
            minimum_atr_pct=0.1,
            required_signals=("CALL", "PUT"),
        ),
        maximum_results=10,
        minimum_composite_score=20.0,
    )

    with TemporaryDirectory() as directory:
        output = Path(directory) / "scan.json"
        scan = MarketScannerService().execute(
            request,
            list(result.candidates),
            output_path=output,
        )
        assert len(scan.ranked_candidates) == 2
        assert output.exists()

    print("All Milestone 34 Phase 1 Step 2 adapter assertions passed.")


if __name__ == "__main__":
    main()

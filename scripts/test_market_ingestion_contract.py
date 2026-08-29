from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile

from trading_ai.market.downloader import MarketDownloader
from trading_ai.market.service import MarketService


@dataclass(frozen=True)
class FakeBar:
    symbol: str
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class FakeProvider:
    def fetch_history(self, symbol: str, start: str, end: str):
        return [
            FakeBar(
                symbol=symbol,
                time=1704067200000,
                open=100.0,
                high=105.0,
                low=99.0,
                close=104.0,
                volume=1000.0,
            )
        ]


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        service = MarketService(
            provider=FakeProvider(),
            cache_dir=Path(temp),
        )

        saved = service.save_history(
            "AAPL",
            start="2024-01-01",
            end="2024-01-02",
        )
        assert saved["symbol"] == "AAPL"
        assert saved["rows"] == 1
        assert Path(saved["cache_file"]).exists()

        cached = service.get_history(
            "AAPL",
            "2024-01-01",
            "2024-01-02",
        )
        assert len(cached) == 1
        assert cached.iloc[0]["close"] == 104.0

        results = MarketDownloader(
            service=service,
            max_workers=2,
        ).run_bulk_download(
            symbols=("AAPL", "MSFT"),
            start="2024-01-01",
            end="2024-01-02",
        )
        assert len(results) == 2
        assert all(result.success for result in results)
        assert all(result.rows == 1 for result in results)

    print(
        "All MarketService save_history and bulk-ingestion "
        "contract assertions passed."
    )


if __name__ == "__main__":
    main()

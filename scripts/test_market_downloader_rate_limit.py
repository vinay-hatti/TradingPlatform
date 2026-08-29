from trading_ai.market.downloader import MarketDownloader


class FakeService:
    def __init__(self):
        self.calls = 0

    def save_history(self, symbol, **kwargs):
        self.calls += 1
        if self.calls < 3:
            raise RuntimeError("HTTP 429 too many requests")
        return {
            "symbol": symbol,
            "rows": 5,
            "cache_file": f".cache/market/{symbol}.pkl",
        }


def main():
    service = FakeService()
    downloader = MarketDownloader(
        service=service,
        max_workers=1,
        request_interval_seconds=0,
        max_retries=3,
        initial_backoff_seconds=0,
        max_backoff_seconds=0,
    )
    result = downloader.run_bulk_download(symbols=("AAPL",))[0]
    assert result.success
    assert result.attempts == 3
    assert service.calls == 3
    print("All Polygon rate-limit retry assertions passed.")


if __name__ == "__main__":
    main()

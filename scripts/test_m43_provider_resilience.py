from datetime import date
from types import SimpleNamespace

from trading_ai.market.providers.polygon import PolygonHistoricalProvider
from trading_ai.scanner.market_data_population.polygon_provider import PolygonBulkHistoricalProvider


class FakeHistoricalProvider:
    def __init__(self):
        self.calls = 0

    def fetch_history(self, symbol, start, end):
        self.calls += 1
        if self.calls < 3:
            raise RuntimeError("429 too many requests")
        return [SimpleNamespace(symbol=symbol, time=1784678400000, open=100, high=101, low=99, close=100.5, volume=1_000_000)]


def main():
    sleeps=[]
    provider=PolygonBulkHistoricalProvider(
        historical_provider=FakeHistoricalProvider(), max_retries=3,
        initial_backoff_seconds=1, max_backoff_seconds=8, jitter_ratio=0,
        rate_limit_cooldown_seconds=2, circuit_breaker_threshold=5,
        circuit_breaker_cooldown_seconds=0, sleep=sleeps.append,
    )
    result=provider.fetch_batch(["AAPL"], date(2026,7,1), date(2026,7,23))
    assert len(result["AAPL"]) == 1
    d=provider.diagnostics()
    assert d["rate_limit_events"] == 2
    assert d["retries"] == 2
    assert sleeps == [2,2]
    assert d["status"] == "RECOVERED"
    print("Milestone 43 Polygon provider resilience assertions passed.")

if __name__ == "__main__": main()

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from trading_ai.market.downloader import MarketDownloader
from trading_ai.market.providers.polygon import PolygonHistoricalProvider


class FakeClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def get_aggs(self, **kwargs):
        return [
            SimpleNamespace(
                timestamp=1785196800000,
                open=100.0,
                high=102.0,
                low=99.0,
                close=101.0,
                volume=1000.0,
            )
        ]


def test_provider_reuses_one_client_per_worker_thread():
    created = []

    def factory(**kwargs):
        client = FakeClient(**kwargs)
        created.append(client)
        return client

    provider = PolygonHistoricalProvider(
        api_key="test",
        client_factory=factory,
        connect_timeout_seconds=5.0,
        read_timeout_seconds=30.0,
        sdk_retries=0,
        pools_per_worker=1,
    )

    def fetch(symbol):
        provider.fetch_history(symbol, "2026-07-01", "2026-07-28")
        provider.fetch_history(symbol, "2026-07-01", "2026-07-28")

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(fetch, ("AAPL", "MSFT")))

    assert 1 <= provider.created_client_count <= 2
    assert len(created) == provider.created_client_count
    for client in created:
        assert client.kwargs["connect_timeout"] == 5.0
        assert client.kwargs["read_timeout"] == 30.0
        assert client.kwargs["retries"] == 0
        assert client.kwargs["num_pools"] == 1


def test_error_classifier_distinguishes_rate_limit_from_connection():
    rate_limit = RuntimeError(
        "MaxRetryError: too many 429 response errors"
    )
    connection = RuntimeError(
        "MaxRetryError: NewConnectionError: name resolution failed"
    )

    assert MarketDownloader._classify_error(rate_limit) == "RATE_LIMIT"
    assert MarketDownloader._classify_error(connection) == "CONNECTION"


def test_network_backoff_is_shorter_than_rate_limit_backoff():
    downloader = MarketDownloader(
        service=object(),
        initial_backoff_seconds=30.0,
        network_backoff_seconds=5.0,
        max_backoff_seconds=300.0,
    )

    network = downloader._backoff(1, "CONNECTION")
    rate_limit = downloader._backoff(1, "RATE_LIMIT")

    assert 5.0 <= network <= 10.0
    assert 60.0 <= rate_limit <= 65.0

from __future__ import annotations

import threading
from typing import Callable, Mapping

from trading_ai.config import settings
from trading_ai.market.dto import MarketBar


class PolygonHistoricalProvider:
    """Thread-safe Polygon aggregate adapter for equity and ETF daily OHLCV.

    A provider instance is shared by ``MarketDownloader`` workers. The official
    Polygon REST client owns an urllib3 connection pool, so sharing one client
    across multiple worker threads can couple transport failures and exhausted
    retries. This adapter therefore creates one long-lived client per worker
    thread and reuses it for every symbol processed by that worker.

    SDK-level retries default to zero. Application-level retries remain under
    ``MarketDownloader`` control so every retry respects the global request
    pacer and can distinguish rate limiting from network failures.
    """

    def __init__(
        self,
        provider_tickers: Mapping[str, str] | None = None,
        *,
        api_key: str | None = None,
        client: object | None = None,
        client_factory: Callable[..., object] | None = None,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 30.0,
        sdk_retries: int = 0,
        pools_per_worker: int = 1,
    ) -> None:
        self.provider_tickers = {
            str(symbol).strip().upper(): str(ticker).strip().upper()
            for symbol, ticker in (provider_tickers or {}).items()
        }
        resolved_key = api_key or getattr(settings, "polygon_api_key", None)
        if client is None and not resolved_key:
            raise RuntimeError(
                "POLYGON_API_KEY is required for equity/ETF OHLCV ingestion"
            )
        if connect_timeout_seconds <= 0:
            raise ValueError("connect_timeout_seconds must be positive")
        if read_timeout_seconds <= 0:
            raise ValueError("read_timeout_seconds must be positive")
        if sdk_retries < 0:
            raise ValueError("sdk_retries cannot be negative")
        if pools_per_worker <= 0:
            raise ValueError("pools_per_worker must be positive")

        self.api_key = str(resolved_key or "")
        self.connect_timeout_seconds = float(connect_timeout_seconds)
        self.read_timeout_seconds = float(read_timeout_seconds)
        self.sdk_retries = int(sdk_retries)
        self.pools_per_worker = int(pools_per_worker)
        self._injected_client = client
        self._client_factory = client_factory
        self._local = threading.local()
        self._client_creation_lock = threading.Lock()
        self._created_clients = 0

    @property
    def created_client_count(self) -> int:
        """Number of worker-local clients created; useful for diagnostics/tests."""
        return self._created_clients

    def _new_client(self) -> object:
        if self._client_factory is not None:
            factory = self._client_factory
        else:
            from polygon import RESTClient
            factory = RESTClient

        client = factory(
            api_key=self.api_key,
            connect_timeout=self.connect_timeout_seconds,
            read_timeout=self.read_timeout_seconds,
            num_pools=self.pools_per_worker,
            retries=self.sdk_retries,
        )
        with self._client_creation_lock:
            self._created_clients += 1
        return client

    def _client(self) -> object:
        # An explicitly injected client is retained for backward-compatible
        # unit tests and single-threaded callers.
        if self._injected_client is not None:
            return self._injected_client

        client = getattr(self._local, "client", None)
        if client is None:
            client = self._new_client()
            self._local.client = client
        return client

    def _resolve_ticker(self, symbol: str) -> str:
        canonical = symbol.strip().upper()
        ticker = self.provider_tickers.get(canonical, canonical)
        # Polygon class-share tickers use dot notation, e.g. BRK.B and BF.B.
        return ticker.replace("-", ".")

    def fetch_history(self, symbol: str, start: str, end: str) -> list[MarketBar]:
        canonical = symbol.strip().upper()
        provider_ticker = self._resolve_ticker(canonical)
        aggregates = self._client().get_aggs(
            ticker=provider_ticker,
            multiplier=1,
            timespan="day",
            from_=start,
            to=end,
            adjusted=True,
            sort="asc",
            limit=50000,
        )
        bars: list[MarketBar] = []
        for aggregate in aggregates:
            if any(
                getattr(aggregate, field, None) is None
                for field in ("timestamp", "open", "high", "low", "close")
            ):
                continue
            bars.append(
                MarketBar(
                    symbol=canonical,
                    time=int(aggregate.timestamp),
                    open=float(aggregate.open),
                    high=float(aggregate.high),
                    low=float(aggregate.low),
                    close=float(aggregate.close),
                    volume=float(getattr(aggregate, "volume", None) or 0.0),
                )
            )
        return bars

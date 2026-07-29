from __future__ import annotations

import threading
from datetime import date
from typing import Callable, Iterable, Mapping

from trading_ai.config import settings
from trading_ai.market.dto import MarketBar


class PolygonHistoricalProvider:
    """Polygon daily OHLCV adapter with worker-local clients and bulk daily support."""

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
        self._canonical_by_provider = {
            ticker.replace("-", "."): symbol
            for symbol, ticker in self.provider_tickers.items()
        }
        resolved_key = api_key or getattr(settings, "polygon_api_key", None)
        if client is None and not resolved_key:
            raise RuntimeError("POLYGON_API_KEY is required for equity/ETF OHLCV ingestion")
        if connect_timeout_seconds <= 0 or read_timeout_seconds <= 0:
            raise ValueError("Polygon timeouts must be positive")
        if sdk_retries < 0 or pools_per_worker <= 0:
            raise ValueError("Polygon retries/pools configuration is invalid")

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
        if self._injected_client is not None:
            return self._injected_client
        client = getattr(self._local, "client", None)
        if client is None:
            client = self._new_client()
            self._local.client = client
        return client

    def _resolve_ticker(self, symbol: str) -> str:
        canonical = symbol.strip().upper()
        return self.provider_tickers.get(canonical, canonical).replace("-", ".")

    def _canonical_symbol(self, provider_ticker: str) -> str:
        normalized = provider_ticker.strip().upper()
        return self._canonical_by_provider.get(normalized, normalized)

    @staticmethod
    def _bar_from_aggregate(symbol: str, aggregate: object) -> MarketBar | None:
        if any(
            getattr(aggregate, field, None) is None
            for field in ("timestamp", "open", "high", "low", "close")
        ):
            return None
        return MarketBar(
            symbol=symbol,
            time=int(getattr(aggregate, "timestamp")),
            open=float(getattr(aggregate, "open")),
            high=float(getattr(aggregate, "high")),
            low=float(getattr(aggregate, "low")),
            close=float(getattr(aggregate, "close")),
            volume=float(getattr(aggregate, "volume", None) or 0.0),
        )

    def fetch_history(self, symbol: str, start: str, end: str) -> list[MarketBar]:
        canonical = symbol.strip().upper()
        aggregates = self._client().get_aggs(
            ticker=self._resolve_ticker(canonical),
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
            bar = self._bar_from_aggregate(canonical, aggregate)
            if bar is not None:
                bars.append(bar)
        return bars

    def fetch_grouped_daily(
        self,
        trading_date: str | date,
        *,
        symbols: Iterable[str] | None = None,
    ) -> list[MarketBar]:
        """Fetch one date for the whole U.S. stock market, then filter canonically."""
        date_text = trading_date.isoformat() if isinstance(trading_date, date) else str(trading_date)
        wanted = None if symbols is None else {str(symbol).strip().upper() for symbol in symbols}
        client = self._client()
        try:
            aggregates = client.get_grouped_daily_aggs(
                date=date_text,
                adjusted=True,
                include_otc=False,
            )
        except TypeError:
            # Compatibility with older polygon client releases.
            aggregates = client.get_grouped_daily_aggs(date=date_text, adjusted=True)

        bars: list[MarketBar] = []
        for aggregate in aggregates:
            provider_ticker = str(
                getattr(aggregate, "ticker", None)
                or getattr(aggregate, "symbol", None)
                or ""
            ).strip().upper()
            if not provider_ticker:
                continue
            canonical = self._canonical_symbol(provider_ticker)
            if wanted is not None and canonical not in wanted:
                continue
            bar = self._bar_from_aggregate(canonical, aggregate)
            if bar is not None:
                bars.append(bar)
        return bars

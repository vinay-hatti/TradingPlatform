from __future__ import annotations

from typing import Mapping

from trading_ai.config import settings
from trading_ai.market.dto import MarketBar


class PolygonHistoricalProvider:
    """Polygon aggregate adapter for equity and ETF daily OHLCV."""

    def __init__(
        self,
        provider_tickers: Mapping[str, str] | None = None,
        *,
        api_key: str | None = None,
        client: object | None = None,
    ) -> None:
        self.provider_tickers = {
            str(symbol).strip().upper(): str(ticker).strip().upper()
            for symbol, ticker in (provider_tickers or {}).items()
        }
        resolved_key = api_key or getattr(settings, "polygon_api_key", None)
        if client is None and not resolved_key:
            raise RuntimeError("POLYGON_API_KEY is required for equity/ETF OHLCV ingestion")
        if client is None:
            from polygon import RESTClient
            client = RESTClient(str(resolved_key))
        self.client = client

    def _resolve_ticker(self, symbol: str) -> str:
        canonical = symbol.strip().upper()
        ticker = self.provider_tickers.get(canonical, canonical)
        # Polygon class-share tickers use dot notation, e.g. BRK.B and BF.B.
        return ticker.replace("-", ".")

    def fetch_history(self, symbol: str, start: str, end: str) -> list[MarketBar]:
        canonical = symbol.strip().upper()
        provider_ticker = self._resolve_ticker(canonical)
        aggregates = self.client.get_aggs(
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

from __future__ import annotations

from typing import Mapping

from trading_ai.config import settings
from trading_ai.market.dto import MarketBar


class PolygonIndexHistoricalProvider:
    """Polygon index aggregate adapter with canonical symbols at the application boundary."""

    def __init__(
        self,
        provider_tickers: Mapping[str, str],
        *,
        api_key: str | None = None,
        client: object | None = None,
    ) -> None:
        self.provider_tickers = {
            str(symbol).strip().upper(): str(ticker).strip().upper()
            for symbol, ticker in provider_tickers.items()
        }
        resolved_key = api_key or getattr(settings, "polygon_api_key", None)
        if client is None and not resolved_key:
            raise RuntimeError("POLYGON_API_KEY is required for index OHLC ingestion")
        if client is None:
            from polygon import RESTClient
            client = RESTClient(str(resolved_key))
        self.client = client

    def fetch_history(self, symbol: str, start: str, end: str) -> list[MarketBar]:
        canonical_symbol = symbol.strip().upper()
        try:
            provider_ticker = self.provider_tickers[canonical_symbol]
        except KeyError as exc:
            raise KeyError(f"No Polygon index ticker mapping for {canonical_symbol}") from exc
        if not provider_ticker.startswith("I:"):
            raise ValueError(f"Polygon index ticker must start with I:: {provider_ticker}")

        aggregates = self.client.get_aggs(
            ticker=provider_ticker,
            multiplier=1,
            timespan="day",
            from_=start,
            to=end,
        )
        bars: list[MarketBar] = []
        for aggregate in aggregates:
            # Cash indices do not have meaningful traded volume. Keep the existing
            # non-null MarketBar contract compatible by normalizing to zero.
            raw_volume = getattr(aggregate, "volume", None)
            bars.append(
                MarketBar(
                    symbol=canonical_symbol,
                    time=aggregate.timestamp,
                    open=float(aggregate.open),
                    high=float(aggregate.high),
                    low=float(aggregate.low),
                    close=float(aggregate.close),
                    volume=float(raw_volume or 0.0),
                )
            )
        return bars

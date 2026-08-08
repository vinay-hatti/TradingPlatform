from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from trading_ai.market.providers.polygon import PolygonHistoricalProvider


class PolygonProvider:
    """Compatibility facade for callers that expect ``history`` and ``quote``."""

    def __init__(self, provider: PolygonHistoricalProvider | None = None) -> None:
        self.provider = provider or PolygonHistoricalProvider()

    @staticmethod
    def _period_start(period: str) -> date:
        today = date.today()
        value = str(period or "1y").strip().lower()
        units = {"d": 1, "wk": 7, "mo": 30, "y": 365}
        for suffix in ("wk", "mo", "y", "d"):
            if value.endswith(suffix):
                try:
                    amount = int(value[: -len(suffix)])
                except ValueError:
                    break
                return today - timedelta(days=max(1, amount * units[suffix]))
        if value in {"ytd"}:
            return date(today.year, 1, 1)
        if value in {"max"}:
            return today - timedelta(days=365 * 20)
        raise ValueError(f"Unsupported period: {period}")

    def history(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        if interval != "1d":
            raise ValueError("Polygon compatibility facade currently supports interval='1d' only")
        end = date.today()
        bars = self.provider.fetch_history(symbol, self._period_start(period).isoformat(), end.isoformat())
        frame = pd.DataFrame([
            {
                "date": pd.to_datetime(bar.time, unit="ms", utc=True),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in bars
        ])
        return frame.sort_values("date").reset_index(drop=True) if not frame.empty else frame

    def quote(self, symbol: str) -> dict:
        client = self.provider._client()
        ticker = self.provider._resolve_ticker(symbol)
        trade = client.get_last_trade(ticker=ticker)
        return {
            "symbol": symbol.strip().upper(),
            "price": float(getattr(trade, "price", 0.0) or 0.0),
            "size": float(getattr(trade, "size", 0.0) or 0.0),
            "timestamp": getattr(trade, "timestamp", None),
            "provider": "POLYGON",
        }

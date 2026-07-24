from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd
import yfinance as yf

from trading_ai.market.provider_routing import DataCapability, ProviderRoutingPolicy


@dataclass(frozen=True)
class YahooHistoricalBar:
    symbol: str
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: int


class YahooHistoricalProvider:
    """Yahoo adapter restricted to underlying OHLCV history."""

    name = "yahoo"
    capability = DataCapability.UNDERLYING_OHLCV

    def __init__(self) -> None:
        ProviderRoutingPolicy.assert_provider(self.capability, self.name)

    def fetch_history(self, symbol: str, start: str, end: str) -> list[YahooHistoricalBar]:
        # yfinance treats end as exclusive; advance it one day so MarketService's
        # inclusive contract remains unchanged.
        inclusive_end = (
            pd.Timestamp(end).date() + timedelta(days=1)
        ).isoformat()
        frame = yf.download(
            symbol,
            start=start,
            end=inclusive_end,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
        if frame is None or frame.empty:
            return []

        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = [
                str(column[0]).lower() if isinstance(column, tuple) else str(column).lower()
                for column in frame.columns
            ]
        else:
            frame.columns = [str(column).lower() for column in frame.columns]

        frame = frame.reset_index()
        date_column = "date" if "date" in frame.columns else frame.columns[0]
        records: list[YahooHistoricalBar] = []
        for _, row in frame.iterrows():
            timestamp = pd.Timestamp(row[date_column])
            records.append(
                YahooHistoricalBar(
                    symbol=symbol.upper().strip(),
                    time=int(timestamp.timestamp() * 1000),
                    open=float(row.get("open", 0.0) or 0.0),
                    high=float(row.get("high", 0.0) or 0.0),
                    low=float(row.get("low", 0.0) or 0.0),
                    close=float(row.get("close", 0.0) or 0.0),
                    volume=int(row.get("volume", 0) or 0),
                )
            )
        return records

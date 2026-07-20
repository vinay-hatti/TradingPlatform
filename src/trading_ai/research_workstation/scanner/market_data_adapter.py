from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Protocol

from sqlalchemy import select

from trading_ai.database import SessionLocal

try:
    # Current TradingPlatform layout: models.py is a module.
    from trading_ai.database.models import PriceHistory
except ImportError:
    # Compatibility with a future package-based model layout.
    from trading_ai.database.models.price_history import PriceHistory


@dataclass(frozen=True)
class MarketBarProfile:
    symbol: str
    trading_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketDataAdapter(Protocol):
    def load_bars(
        self,
        *,
        symbols: Iterable[str],
        start: date | None = None,
        end: date | None = None,
    ) -> dict[str, tuple[MarketBarProfile, ...]]:
        ...


class PriceHistoryMarketDataAdapter:
    def __init__(self, session_factory=SessionLocal):
        self._session_factory = session_factory

    def load_bars(
        self,
        *,
        symbols: Iterable[str],
        start: date | None = None,
        end: date | None = None,
    ) -> dict[str, tuple[MarketBarProfile, ...]]:
        normalized = tuple(
            dict.fromkeys(
                symbol.strip().upper()
                for symbol in symbols
                if symbol and symbol.strip()
            )
        )
        if not normalized:
            return {}

        statement = select(PriceHistory).where(
            PriceHistory.symbol.in_(normalized)
        )

        if start is not None:
            statement = statement.where(PriceHistory.date >= start)

        if end is not None:
            statement = statement.where(PriceHistory.date <= end)

        statement = statement.order_by(
            PriceHistory.symbol,
            PriceHistory.date,
        )

        grouped: dict[str, list[MarketBarProfile]] = {
            symbol: [] for symbol in normalized
        }

        with self._session_factory() as session:
            rows = session.execute(statement).scalars().all()

        for row in rows:
            grouped.setdefault(row.symbol, []).append(
                MarketBarProfile(
                    symbol=row.symbol,
                    trading_date=row.date,
                    open=float(row.open),
                    high=float(row.high),
                    low=float(row.low),
                    close=float(row.close),
                    volume=int(row.volume),
                )
            )

        return {
            symbol: tuple(values)
            for symbol, values in grouped.items()
        }

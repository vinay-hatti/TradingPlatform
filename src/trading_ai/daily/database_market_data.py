from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

import pandas as pd
from sqlalchemy import func, select

from trading_ai.database import SessionLocal
from trading_ai.market.models import PriceHistory


class DatabaseMarketDataError(RuntimeError):
    """Base error for scanner database-market-data failures."""


class DatabaseMarketDataUnavailableError(DatabaseMarketDataError):
    """Raised when PostgreSQL has no usable price history for a scan symbol."""


@dataclass(frozen=True)
class EffectiveHistoryWindow:
    requested_start: date
    requested_end: date
    effective_start: date
    effective_end: date
    stored_symbol: str
    row_count: int


class DatabaseHistoricalDataSource:
    """Read-only scanner data source backed exclusively by ``price_history``.

    This class intentionally has no provider, cache, refresh, or persistence
    dependencies. It is the market-data boundary used by the Daily Scanner.
    """

    _INDEX_ALIASES: dict[str, tuple[str, ...]] = {
        "SPX": ("SPX", "^SPX", "I:SPX", "$SPX"),
        "NDX": ("NDX", "^NDX", "I:NDX", "$NDX"),
        "RUT": ("RUT", "^RUT", "I:RUT", "$RUT"),
        "DJI": ("DJI", "^DJI", "I:DJI", "$DJI"),
        "VIX": ("VIX", "^VIX", "I:VIX", "$VIX"),
    }

    def __init__(self, *, maximum_as_of_date: str | date | datetime | None = None) -> None:
        self.maximum_as_of_date = (
            self._to_date(maximum_as_of_date)
            if maximum_as_of_date is not None
            else None
        )
        self._windows: dict[str, EffectiveHistoryWindow] = {}

    @staticmethod
    def _to_date(value: str | date | datetime) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])

    @classmethod
    def symbol_candidates(cls, symbol: str) -> tuple[str, ...]:
        normalized = str(symbol).strip().upper()
        if not normalized:
            raise ValueError("symbol is required")

        base = normalized.removeprefix("$").removeprefix("^")
        if base.startswith("I:"):
            base = base[2:]

        candidates: list[str] = []

        def add(value: str) -> None:
            value = value.strip().upper()
            if value and value not in candidates:
                candidates.append(value)

        for value in cls._INDEX_ALIASES.get(base, ()):
            add(value)
        add(normalized)
        add(base)
        add(base.replace("_", "."))
        add(base.replace(".", "_"))
        add(base.replace(".", "-"))
        return tuple(candidates)

    def _requested_window(
        self,
        start: str | date | datetime,
        end: str | date | datetime,
    ) -> tuple[date, date]:
        requested_start = self._to_date(start)
        requested_end = self._to_date(end)
        if requested_start > requested_end:
            raise ValueError(
                f"start date {requested_start} cannot be after {requested_end}"
            )
        if self.maximum_as_of_date is not None:
            requested_end = min(requested_end, self.maximum_as_of_date)
        if requested_start > requested_end:
            raise DatabaseMarketDataUnavailableError(
                "Requested history starts after the latest published market date: "
                f"{requested_start} > {requested_end}."
            )
        return requested_start, requested_end

    @staticmethod
    def _pick_stored_symbol(
        counts: Iterable[tuple[str, int]],
        candidates: tuple[str, ...],
    ) -> str | None:
        by_symbol = {str(symbol).upper(): int(count) for symbol, count in counts}
        eligible = [(symbol, by_symbol.get(symbol, 0)) for symbol in candidates]
        eligible = [item for item in eligible if item[1] > 0]
        if not eligible:
            return None
        eligible.sort(key=lambda item: (-item[1], candidates.index(item[0])))
        return eligible[0][0]

    def get_price_history(
        self,
        symbol: str,
        start: str | date | datetime,
        end: str | date | datetime,
    ) -> pd.DataFrame:
        requested_start = self._to_date(start)
        raw_requested_end = self._to_date(end)
        effective_query_start, effective_query_end = self._requested_window(start, end)
        candidates = self.symbol_candidates(symbol)

        with SessionLocal() as session:
            count_stmt = (
                select(PriceHistory.symbol, func.count())
                .where(
                    func.upper(PriceHistory.symbol).in_(candidates),
                    PriceHistory.date >= effective_query_start,
                    PriceHistory.date <= effective_query_end,
                )
                .group_by(PriceHistory.symbol)
            )
            stored_symbol = self._pick_stored_symbol(
                session.execute(count_stmt).all(), candidates
            )
            if stored_symbol is None:
                available_stmt = select(
                    func.min(PriceHistory.date),
                    func.max(PriceHistory.date),
                ).where(func.upper(PriceHistory.symbol).in_(candidates))
                available_start, available_end = session.execute(available_stmt).one()
                if available_start is None:
                    detail = "no rows exist for any recognized symbol alias"
                else:
                    detail = (
                        f"available rows span {available_start} -> {available_end}, "
                        "outside the effective request"
                    )
                raise DatabaseMarketDataUnavailableError(
                    "No PostgreSQL price_history rows are available for "
                    f"{symbol} during {effective_query_start} -> {effective_query_end}; "
                    f"{detail}. Recognized aliases: {', '.join(candidates)}."
                )

            rows_stmt = (
                select(PriceHistory)
                .where(
                    func.upper(PriceHistory.symbol) == stored_symbol,
                    PriceHistory.date >= effective_query_start,
                    PriceHistory.date <= effective_query_end,
                )
                .order_by(PriceHistory.date)
            )
            rows = list(session.scalars(rows_stmt))

        if not rows:
            raise DatabaseMarketDataUnavailableError(
                f"PostgreSQL returned no usable price_history rows for {symbol}."
            )

        effective_start = rows[0].date
        effective_end = rows[-1].date
        self._windows[str(symbol).upper()] = EffectiveHistoryWindow(
            requested_start=requested_start,
            requested_end=raw_requested_end,
            effective_start=effective_start,
            effective_end=effective_end,
            stored_symbol=stored_symbol,
            row_count=len(rows),
        )

        return pd.DataFrame(
            {
                "symbol": [row.symbol for row in rows],
                "date": [row.date for row in rows],
                "time": [
                    int(datetime.combine(row.date, datetime.min.time()).timestamp() * 1000)
                    for row in rows
                ],
                "open": [row.open for row in rows],
                "high": [row.high for row in rows],
                "low": [row.low for row in rows],
                "close": [row.close for row in rows],
                "volume": [row.volume for row in rows],
            }
        )

    def effective_window(self, symbol: str) -> EffectiveHistoryWindow | None:
        return self._windows.get(str(symbol).strip().upper())

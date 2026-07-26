from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Iterable

from trading_ai.market.dto import MarketBar


@dataclass(frozen=True)
class IndexHistoryIngestionResult:
    symbol: str
    success: bool
    downloaded_rows: int
    persisted_rows: int
    inserted_rows: int
    updated_rows: int
    attempts: int
    start_date: date
    end_date: date
    error: str | None = None


@dataclass(frozen=True)
class IndexHistoryIngestionProfile:
    results: tuple[IndexHistoryIngestionResult, ...]

    @property
    def failed_count(self) -> int:
        return sum(not result.success for result in self.results)

    @property
    def persisted_rows(self) -> int:
        return sum(result.persisted_rows for result in self.results)


class IndexHistoryIngestionService:
    """Fetches Polygon index bars and atomically persists canonical PriceHistory rows."""

    def __init__(
        self,
        *,
        provider,
        session_factory: Callable[[], object],
        max_retries: int = 5,
        initial_backoff_seconds: float = 30.0,
        max_backoff_seconds: float = 300.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.provider = provider
        self.session_factory = session_factory
        self.max_retries = max(1, int(max_retries))
        self.initial_backoff_seconds = max(0.0, float(initial_backoff_seconds))
        self.max_backoff_seconds = max(
            self.initial_backoff_seconds,
            float(max_backoff_seconds),
        )
        self.sleep = sleep

    def run(
        self,
        *,
        symbols: Iterable[str],
        start: str | date | None,
        end: str | date | None,
        lookback_days: int,
        continue_on_error: bool,
    ) -> IndexHistoryIngestionProfile:
        start_date, end_date = self._resolve_range(start, end, lookback_days)
        results: list[IndexHistoryIngestionResult] = []
        for raw_symbol in symbols:
            symbol = str(raw_symbol).strip().upper()
            result = self._ingest_symbol(symbol, start_date, end_date)
            results.append(result)
            if not result.success and not continue_on_error:
                raise RuntimeError(result.error or f"Index ingestion failed for {symbol}")
        return IndexHistoryIngestionProfile(tuple(results))

    def _ingest_symbol(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> IndexHistoryIngestionResult:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                bars = list(
                    self.provider.fetch_history(
                        symbol,
                        start_date.isoformat(),
                        end_date.isoformat(),
                    )
                )
                if not bars:
                    raise RuntimeError("provider returned zero rows")
                normalized = self._normalize_bars(symbol, bars)
                inserted, updated, persisted = self._persist(symbol, normalized)
                if persisted != len(normalized):
                    raise RuntimeError(
                        f"persistence verification failed: downloaded={len(normalized)}, "
                        f"persisted={persisted}"
                    )
                return IndexHistoryIngestionResult(
                    symbol=symbol,
                    success=True,
                    downloaded_rows=len(normalized),
                    persisted_rows=persisted,
                    inserted_rows=inserted,
                    updated_rows=updated,
                    attempts=attempt,
                    start_date=start_date,
                    end_date=end_date,
                )
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    delay = min(
                        self.initial_backoff_seconds * (2 ** (attempt - 1)),
                        self.max_backoff_seconds,
                    )
                    if delay > 0:
                        self.sleep(delay)
        return IndexHistoryIngestionResult(
            symbol=symbol,
            success=False,
            downloaded_rows=0,
            persisted_rows=0,
            inserted_rows=0,
            updated_rows=0,
            attempts=self.max_retries,
            start_date=start_date,
            end_date=end_date,
            error=f"{type(last_error).__name__}: {last_error}" if last_error else "unknown error",
        )

    def _persist(self, symbol: str, bars: list[MarketBar]) -> tuple[int, int, int]:
        from sqlalchemy import func, select
        from trading_ai.market.models import PriceHistory

        session = self.session_factory()
        try:
            bar_dates = [self._bar_date(bar) for bar in bars]
            existing_dates = set(
                session.scalars(
                    select(PriceHistory.date).where(
                        PriceHistory.symbol == symbol,
                        PriceHistory.date.in_(bar_dates),
                    )
                )
            )
            for bar in bars:
                bar_date = self._bar_date(bar)
                session.merge(
                    PriceHistory(
                        symbol=symbol,
                        date=bar_date,
                        open=float(bar.open),
                        high=float(bar.high),
                        low=float(bar.low),
                        close=float(bar.close),
                        volume=float(bar.volume or 0.0),
                    )
                )
            session.commit()
            persisted = int(
                session.scalar(
                    select(func.count()).select_from(PriceHistory).where(
                        PriceHistory.symbol == symbol,
                        PriceHistory.date.in_(bar_dates),
                    )
                )
                or 0
            )
            inserted = len(set(bar_dates) - existing_dates)
            updated = len(set(bar_dates) & existing_dates)
            return inserted, updated, persisted
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _normalize_bars(symbol: str, bars: list[MarketBar]) -> list[MarketBar]:
        by_date: dict[date, MarketBar] = {}
        for bar in bars:
            if str(bar.symbol).strip().upper() != symbol:
                raise ValueError(
                    f"Provider returned non-canonical symbol {bar.symbol!r} for {symbol}"
                )
            bar_date = IndexHistoryIngestionService._bar_date(bar)
            values = (bar.open, bar.high, bar.low, bar.close)
            if any(value is None for value in values):
                raise ValueError(f"Incomplete OHLC bar for {symbol} on {bar_date}")
            if float(bar.high) < float(bar.low):
                raise ValueError(f"Invalid high/low bar for {symbol} on {bar_date}")
            by_date[bar_date] = bar
        return [by_date[key] for key in sorted(by_date)]

    @staticmethod
    def _bar_date(bar: MarketBar) -> date:
        raw = bar.time
        if isinstance(raw, datetime):
            return raw.date()
        if isinstance(raw, date):
            return raw
        numeric = float(raw)
        if numeric > 10_000_000_000:
            numeric /= 1000.0
        return datetime.fromtimestamp(numeric, tz=timezone.utc).date()

    @staticmethod
    def _resolve_range(
        start: str | date | None,
        end: str | date | None,
        lookback_days: int,
    ) -> tuple[date, date]:
        end_date = IndexHistoryIngestionService._parse_date(end) or date.today()
        start_date = IndexHistoryIngestionService._parse_date(start)
        if start_date is None:
            start_date = end_date - timedelta(days=max(1, int(lookback_days)))
        if start_date > end_date:
            raise ValueError(f"start date {start_date} is after end date {end_date}")
        return start_date, end_date

    @staticmethod
    def _parse_date(value: str | date | None) -> date | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

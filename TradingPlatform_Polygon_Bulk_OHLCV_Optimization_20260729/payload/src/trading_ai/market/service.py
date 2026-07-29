from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import pickle
import re
from typing import Any, Callable, Iterable

import pandas as pd
from sqlalchemy import func, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert


class MarketDataNotCachedError(RuntimeError):
    pass


_CACHE_FILE_RE = re.compile(
    r"^(?P<symbol>.+)_(?P<start>\d{4}-\d{2}-\d{2})_(?P<end>\d{4}-\d{2}-\d{2})\.pkl$"
)


class MarketService:
    def __init__(
        self,
        provider: Any | None = None,
        cache_dir: str | Path = ".cache/market/polygon",
        session_factory: Callable[[], Any] | None = None,
        *,
        cache_enabled: bool = False,
    ) -> None:
        if provider is None:
            from trading_ai.market.providers.polygon import PolygonHistoricalProvider
            provider = PolygonHistoricalProvider()
        if session_factory is None:
            from trading_ai.database import SessionLocal
            session_factory = SessionLocal
        self.provider = provider
        self.session_factory = session_factory
        self.cache_enabled = bool(cache_enabled)
        self.cache_dir = Path(cache_dir)
        if self.cache_enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize_date(value: str | date | datetime) -> str:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    def _cache_file(self, symbol: str, start: str, end: str) -> Path:
        return self.cache_dir / f"{symbol}_{start}_{end}.pkl"

    @staticmethod
    def _frame_dates(df: pd.DataFrame) -> pd.Series:
        if "time" in df.columns:
            return pd.to_datetime(df["time"], unit="ms", errors="coerce", utc=True)
        if "date" in df.columns:
            return pd.to_datetime(df["date"], errors="coerce", utc=True)
        return pd.Series(pd.to_datetime(df.index, errors="coerce", utc=True), index=df.index)

    def _load_cached_df(self, symbol: str, start: str, end: str) -> pd.DataFrame | None:
        if not self.cache_enabled:
            return None
        exact = self._cache_file(symbol, start, end)
        if not exact.exists():
            return None
        try:
            with exact.open("rb") as handle:
                frame = pickle.load(handle)
        except (OSError, EOFError, pickle.PickleError, ValueError, TypeError):
            return None
        return frame if isinstance(frame, pd.DataFrame) and not frame.empty else None

    def _write_cache(self, symbol: str, start: str, end: str, frame: pd.DataFrame) -> str:
        if not self.cache_enabled:
            return ""
        cache_file = self._cache_file(symbol, start, end)
        temp_file = cache_file.with_suffix(".pkl.tmp")
        with temp_file.open("wb") as handle:
            pickle.dump(frame, handle)
        temp_file.replace(cache_file)
        return str(cache_file)

    @staticmethod
    def _bars_frame(bars: Iterable[Any]) -> pd.DataFrame:
        frame = pd.DataFrame([
            {
                "symbol": bar.symbol,
                "time": bar.time,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in bars
        ])
        if frame.empty:
            return frame
        return (
            frame.sort_values(["symbol", "time"])
            .drop_duplicates(subset=["symbol", "time"], keep="last")
            .reset_index(drop=True)
        )

    def get_history(
        self,
        symbol: str,
        start: str | date | datetime,
        end: str | date | datetime,
        *,
        force_refresh: bool = False,
        cache_only: bool = False,
    ) -> pd.DataFrame:
        symbol = symbol.upper().strip()
        start_text = self._normalize_date(start)
        end_text = self._normalize_date(end)
        if not symbol:
            raise ValueError("symbol is required")
        if start_text > end_text:
            raise ValueError(f"start date {start_text} cannot be after {end_text}")
        if not force_refresh:
            cached = self._load_cached_df(symbol, start_text, end_text)
            if cached is not None:
                return cached
        if cache_only:
            raise MarketDataNotCachedError(
                "Underlying file cache is disabled or unavailable; PostgreSQL price_history is authoritative."
            )
        frame = self._bars_frame(self.provider.fetch_history(symbol, start_text, end_text))
        self._write_cache(symbol, start_text, end_text, frame)
        return frame

    @classmethod
    def _persistence_rows(cls, frame: pd.DataFrame) -> list[dict[str, Any]]:
        if frame.empty:
            return []
        dates = cls._frame_dates(frame)
        rows: list[dict[str, Any]] = []
        for position, (_, record) in enumerate(frame.iterrows()):
            timestamp = dates.iloc[position]
            if pd.isna(timestamp):
                continue
            row = {
                "symbol": str(record["symbol"]).strip().upper(),
                "date": timestamp.date(),
                "open": float(record["open"]),
                "high": float(record["high"]),
                "low": float(record["low"]),
                "close": float(record["close"]),
                "volume": float(record.get("volume") or 0.0),
            }
            if row["high"] < row["low"]:
                raise ValueError(f"Invalid OHLC row for {row['symbol']} {row['date']}: high < low")
            rows.append(row)
        return rows

    def latest_dates(self, symbols: Iterable[str]) -> dict[str, date | None]:
        from trading_ai.market.models import PriceHistory
        selected = tuple(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
        result = {symbol: None for symbol in selected}
        if not selected:
            return result
        session = self.session_factory()
        try:
            rows = session.execute(
                select(PriceHistory.symbol, func.max(PriceHistory.date))
                .where(PriceHistory.symbol.in_(selected))
                .group_by(PriceHistory.symbol)
            ).all()
            for symbol, latest in rows:
                result[str(symbol).upper()] = latest
            return result
        finally:
            session.close()

    def _upsert_price_history(self, rows: list[dict[str, Any]]) -> dict[str, int]:
        if not rows:
            return {"persisted": 0, "inserted": 0, "updated": 0}
        from trading_ai.market.models import PriceHistory
        # Deduplicate before hitting PostgreSQL so one grouped payload cannot
        # produce an ON CONFLICT row-touched-twice error.
        deduped = list({(r["symbol"], r["date"]): r for r in rows}.values())
        keys = [(r["symbol"], r["date"]) for r in deduped]
        session = self.session_factory()
        try:
            existing: set[tuple[str, date]] = set()
            for offset in range(0, len(keys), 2000):
                chunk = keys[offset:offset + 2000]
                existing.update(
                    (str(symbol).upper(), row_date)
                    for symbol, row_date in session.execute(
                        select(PriceHistory.symbol, PriceHistory.date).where(
                            tuple_(PriceHistory.symbol, PriceHistory.date).in_(chunk)
                        )
                    ).all()
                )
            for offset in range(0, len(deduped), 5000):
                chunk_rows = deduped[offset:offset + 5000]
                statement = pg_insert(PriceHistory).values(chunk_rows)
                statement = statement.on_conflict_do_update(
                    index_elements=[PriceHistory.symbol, PriceHistory.date],
                    set_={
                        "open": statement.excluded.open,
                        "high": statement.excluded.high,
                        "low": statement.excluded.low,
                        "close": statement.excluded.close,
                        "volume": statement.excluded.volume,
                    },
                )
                session.execute(statement)
            session.commit()
            updated = len(existing)
            return {
                "persisted": len(deduped),
                "inserted": len(deduped) - updated,
                "updated": updated,
            }
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def save_grouped_daily(self, symbols: Iterable[str], trading_date: str | date) -> dict[str, Any]:
        selected = tuple(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
        bars = self.provider.fetch_grouped_daily(trading_date, symbols=selected)
        frame = self._bars_frame(bars)
        rows = self._persistence_rows(frame)
        counts = self._upsert_price_history(rows)
        by_symbol: dict[str, int] = {}
        for row in rows:
            by_symbol[row["symbol"]] = by_symbol.get(row["symbol"], 0) + 1
        return {
            "date": self._normalize_date(trading_date),
            "downloaded_rows": len(frame),
            "persisted_rows": counts["persisted"],
            "inserted_rows": counts["inserted"],
            "updated_rows": counts["updated"],
            "symbols_with_bars": by_symbol,
            "provider": type(self.provider).__name__,
        }

    def save_history(
        self,
        symbol: str,
        start: str | date | datetime | None = None,
        end: str | date | datetime | None = None,
        *,
        lookback_days: int = 730,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        if lookback_days <= 0:
            raise ValueError("lookback_days must be positive")
        end_date = date.today() if end is None else date.fromisoformat(self._normalize_date(end))
        start_date = end_date - timedelta(days=lookback_days) if start is None else date.fromisoformat(self._normalize_date(start))
        frame = self.get_history(symbol, start_date, end_date, force_refresh=force_refresh, cache_only=False)
        rows = self._persistence_rows(frame)
        counts = self._upsert_price_history(rows)
        return {
            "symbol": symbol.upper().strip(),
            "provider": type(self.provider).__name__,
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "rows": len(frame),
            "downloaded_rows": len(frame),
            "persisted_rows": counts["persisted"],
            "inserted_rows": counts["inserted"],
            "updated_rows": counts["updated"],
            "cache_file": self._write_cache(symbol.upper().strip(), start_date.isoformat(), end_date.isoformat(), frame),
        }

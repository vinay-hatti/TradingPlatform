from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import pickle
import re
from typing import Any

import pandas as pd


class MarketDataNotCachedError(RuntimeError):
    pass


_CACHE_FILE_RE = re.compile(
    r"^(?P<symbol>.+)_(?P<start>\d{4}-\d{2}-\d{2})_"
    r"(?P<end>\d{4}-\d{2}-\d{2})\.pkl$"
)


class MarketService:
    def __init__(
        self,
        provider: Any | None = None,
        cache_dir: str | Path = ".cache/market",
    ) -> None:
        if provider is None:
            from trading_ai.market.providers.yahoo import YahooHistoricalProvider
            provider = YahooHistoricalProvider()

        self.provider = provider
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize_date(value: str | date | datetime) -> str:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    def _cache_file(
        self,
        symbol: str,
        start: str,
        end: str,
    ) -> Path:
        return self.cache_dir / f"{symbol}_{start}_{end}.pkl"

    @staticmethod
    def _parse_cache_range(
        path: Path,
        symbol: str,
    ) -> tuple[str, str] | None:
        match = _CACHE_FILE_RE.match(path.name)
        if not match:
            return None

        cached_symbol = match.group("symbol")
        if cached_symbol != symbol:
            return None

        return match.group("start"), match.group("end")

    @staticmethod
    def _frame_dates(df: pd.DataFrame) -> pd.Series:
        if "time" in df.columns:
            return pd.to_datetime(
                df["time"],
                unit="ms",
                errors="coerce",
                utc=True,
            )

        if "date" in df.columns:
            return pd.to_datetime(
                df["date"],
                errors="coerce",
                utc=True,
            )

        return pd.Series(
            pd.to_datetime(
                df.index,
                errors="coerce",
                utc=True,
            ),
            index=df.index,
        )

    @classmethod
    def _slice_frame(
        cls,
        df: pd.DataFrame,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        dates = cls._frame_dates(df)
        valid = dates.notna()

        if not valid.any():
            return df.copy().reset_index(drop=True)

        date_strings = dates.dt.date.astype(str)
        mask = valid & date_strings.ge(start) & date_strings.le(end)
        return df.loc[mask].reset_index(drop=True)

    def _load_cached_df(
        self,
        symbol: str,
        start: str,
        end: str,
    ) -> pd.DataFrame | None:
        """
        Load any non-empty cache file whose requested range covers the scan.

        The requested range comes from the filename, not the final returned bar.
        The OHLCV provider may not return today's bar until after the session closes, and
        weekends/holidays naturally have no bar even when the request itself
        covered that date.
        """
        exact = self._cache_file(symbol, start, end)
        candidates: list[Path] = []

        if exact.exists():
            candidates.append(exact)

        candidates.extend(
            file
            for file in self.cache_dir.glob(f"{symbol}_*.pkl")
            if file != exact
        )

        covering: list[tuple[int, Path, pd.DataFrame]] = []

        for file in candidates:
            cache_range = self._parse_cache_range(file, symbol)
            if cache_range is None:
                continue

            cached_start, cached_end = cache_range
            if cached_start > start or cached_end < end:
                continue

            try:
                with file.open("rb") as handle:
                    frame = pickle.load(handle)
            except (
                OSError,
                EOFError,
                pickle.PickleError,
                ValueError,
                TypeError,
            ):
                continue

            if not isinstance(frame, pd.DataFrame) or frame.empty:
                continue

            sliced = self._slice_frame(frame, start, end)

            # A request ending on today/weekend/holiday can legitimately have
            # its final bar before `end`. Keep the non-empty requested cache.
            if sliced.empty:
                continue

            covering.append((len(sliced), file, sliced))

        if not covering:
            return None

        # Prefer the cache that provides the most usable rows.
        covering.sort(key=lambda item: item[0], reverse=True)
        return covering[0][2]

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
            raise ValueError(
                f"start date {start_text} cannot be after {end_text}"
            )

        if not force_refresh:
            cached = self._load_cached_df(
                symbol,
                start_text,
                end_text,
            )
            if cached is not None:
                return cached

        if cache_only:
            raise MarketDataNotCachedError(
                f"No non-empty cached market data covers {symbol} "
                f"{start_text} -> {end_text}. Run ingest-market first."
            )

        bars = self.provider.fetch_history(
            symbol,
            start_text,
            end_text,
        )

        frame = pd.DataFrame(
            [
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
            ]
        )

        if not frame.empty:
            frame = (
                frame.sort_values("time")
                .drop_duplicates(
                    subset=["symbol", "time"],
                    keep="last",
                )
                .reset_index(drop=True)
            )

        cache_file = self._cache_file(
            symbol,
            start_text,
            end_text,
        )
        temp_file = cache_file.with_suffix(".pkl.tmp")

        with temp_file.open("wb") as handle:
            pickle.dump(frame, handle)

        temp_file.replace(cache_file)
        return frame

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

        end_date = (
            date.today()
            if end is None
            else date.fromisoformat(self._normalize_date(end))
        )
        start_date = (
            end_date - timedelta(days=lookback_days)
            if start is None
            else date.fromisoformat(self._normalize_date(start))
        )

        frame = self.get_history(
            symbol,
            start_date,
            end_date,
            force_refresh=force_refresh,
            cache_only=False,
        )

        return {
            "symbol": symbol.upper().strip(),
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "rows": len(frame),
            "cache_file": str(
                self._cache_file(
                    symbol.upper().strip(),
                    start_date.isoformat(),
                    end_date.isoformat(),
                )
            ),
        }

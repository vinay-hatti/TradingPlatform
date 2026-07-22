from __future__ import annotations

import gc
from datetime import date
from pathlib import Path
from typing import Sequence

import pandas as pd
import yfinance as yf

from .models import PriceBar


class YFinanceBulkHistoricalProvider:
    """Bounded-resource yfinance provider.

    yfinance's threaded downloader can create enough sockets/cache handles to
    exhaust macOS's default descriptor limit when a large universe is processed.
    This adapter deliberately downloads small chunks with threads disabled and
    releases each DataFrame before continuing.
    """

    def __init__(
        self,
        *,
        cache_dir: str | Path = 'data/cache/yfinance',
        provider_chunk_size: int = 10,
        timeout_seconds: float = 30.0,
    ) -> None:
        if provider_chunk_size < 1:
            raise ValueError('provider_chunk_size must be positive')
        if timeout_seconds <= 0:
            raise ValueError('timeout_seconds must be positive')
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.provider_chunk_size = provider_chunk_size
        self.timeout_seconds = timeout_seconds
        # Prevent yfinance from attempting to create its SQLite cache in an
        # unavailable or transient default directory.
        yf.set_tz_cache_location(str(self.cache_dir.resolve()))

    @property
    def name(self) -> str:
        return 'YFINANCE'

    @staticmethod
    def _bars_for_symbol(frame: pd.DataFrame, symbol: str) -> tuple[PriceBar, ...]:
        if frame.empty:
            return ()
        data = frame
        if isinstance(frame.columns, pd.MultiIndex):
            levels = [set(map(str, frame.columns.get_level_values(i))) for i in range(frame.columns.nlevels)]
            if symbol in levels[0]:
                data = frame[symbol]
            elif symbol in levels[-1]:
                data = frame.xs(symbol, axis=1, level=-1)
            else:
                return ()
        rename = {str(c).lower().replace(' ', '_'): c for c in data.columns}
        required = ['open', 'high', 'low', 'close', 'volume']
        if any(key not in rename for key in required):
            return ()
        bars: list[PriceBar] = []
        for idx, row in data.iterrows():
            values = [row[rename[key]] for key in required]
            if any(pd.isna(value) for value in values):
                continue
            ts = pd.Timestamp(idx)
            bars.append(PriceBar(
                symbol=symbol,
                date=ts.date(),
                open=float(values[0]),
                high=float(values[1]),
                low=float(values[2]),
                close=float(values[3]),
                volume=float(values[4]),
            ))
        return tuple(bars)

    def _download_chunk(
        self,
        symbols: Sequence[str],
        start: date,
        end: date,
    ) -> dict[str, tuple[PriceBar, ...]]:
        frame: pd.DataFrame | None = None
        try:
            frame = yf.download(
                tickers=list(symbols),
                start=start.isoformat(),
                end=end.isoformat(),
                interval='1d',
                auto_adjust=False,
                group_by='ticker',
                # Critical stability fix: do not fan out one thread/socket per ticker.
                threads=False,
                progress=False,
                actions=False,
                timeout=self.timeout_seconds,
                multi_level_index=True,
            )
            if frame is None:
                return {symbol: () for symbol in symbols}
            return {symbol: self._bars_for_symbol(frame, symbol) for symbol in symbols}
        finally:
            if frame is not None:
                del frame
            gc.collect()

    def fetch_batch(self, symbols: Sequence[str], start: date, end: date) -> dict[str, tuple[PriceBar, ...]]:
        selected = tuple(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
        output: dict[str, tuple[PriceBar, ...]] = {}
        for offset in range(0, len(selected), self.provider_chunk_size):
            chunk = selected[offset:offset + self.provider_chunk_size]
            output.update(self._download_chunk(chunk, start, end))
        return output

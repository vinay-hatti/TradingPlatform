from __future__ import annotations

import contextlib
import gc
import io
import random
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Sequence

import pandas as pd
import yfinance as yf

from .models import PriceBar


@dataclass
class ProviderDiagnostics:
    provider: str = "YFINANCE"
    status: str = "HEALTHY"
    requests: int = 0
    retries: int = 0
    rate_limit_events: int = 0
    circuit_open_events: int = 0
    suppressed_log_lines: int = 0
    affected_symbols: set[str] = field(default_factory=set)
    last_error: str = ""

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "status": self.status,
            "requests": self.requests,
            "retries": self.retries,
            "rate_limit_events": self.rate_limit_events,
            "circuit_open_events": self.circuit_open_events,
            "suppressed_log_lines": self.suppressed_log_lines,
            "affected_symbols": sorted(self.affected_symbols),
            "last_error": self.last_error,
        }


class YFinanceBulkHistoricalProvider:
    """Bounded-resource yfinance provider with provider-aware resilience.

    yfinance may route some requests through upstream services that emit one
    stderr line per failed ticker. This adapter captures those implementation
    details, classifies rate limiting, and exposes one structured diagnostic
    summary to the orchestration layer.
    """

    def __init__(
        self,
        *,
        cache_dir: str | Path = 'data/cache/yfinance',
        provider_chunk_size: int = 10,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        initial_backoff_seconds: float = 2.0,
        max_backoff_seconds: float = 60.0,
        jitter_ratio: float = 0.20,
        rate_limit_cooldown_seconds: float = 15.0,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_cooldown_seconds: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
        random_value: Callable[[], float] = random.random,
    ) -> None:
        if provider_chunk_size < 1:
            raise ValueError('provider_chunk_size must be positive')
        if timeout_seconds <= 0:
            raise ValueError('timeout_seconds must be positive')
        if max_retries < 0:
            raise ValueError('max_retries cannot be negative')
        if initial_backoff_seconds < 0 or max_backoff_seconds < 0:
            raise ValueError('backoff values cannot be negative')
        if max_backoff_seconds < initial_backoff_seconds:
            raise ValueError('max_backoff_seconds cannot be below initial_backoff_seconds')
        if not 0 <= jitter_ratio <= 1:
            raise ValueError('jitter_ratio must be between 0 and 1')
        if circuit_breaker_threshold < 1:
            raise ValueError('circuit_breaker_threshold must be positive')
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.provider_chunk_size = provider_chunk_size
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.initial_backoff_seconds = initial_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.jitter_ratio = jitter_ratio
        self.rate_limit_cooldown_seconds = rate_limit_cooldown_seconds
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_cooldown_seconds = circuit_breaker_cooldown_seconds
        self._sleep = sleep
        self._random = random_value
        self._consecutive_rate_limits = 0
        self._diagnostics = ProviderDiagnostics()
        yf.set_tz_cache_location(str(self.cache_dir.resolve()))

    @property
    def name(self) -> str:
        return 'YFINANCE'

    @staticmethod
    def _is_rate_limit(message: str) -> bool:
        value = message.lower()
        return any(token in value for token in ('429', 'too many requests', 'rate limit', 'ratelimit'))

    def _delay(self, retry_number: int, rate_limited: bool) -> float:
        base = self.initial_backoff_seconds * (2 ** max(0, retry_number - 1))
        if rate_limited:
            base = max(base, self.rate_limit_cooldown_seconds)
        capped = min(base, self.max_backoff_seconds)
        jitter = capped * self.jitter_ratio * self._random()
        return capped + jitter

    def diagnostics(self) -> dict:
        return self._diagnostics.to_dict()

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
            bars.append(PriceBar(symbol=symbol, date=ts.date(), open=float(values[0]), high=float(values[1]), low=float(values[2]), close=float(values[3]), volume=float(values[4])))
        return tuple(bars)

    def _download_once(self, symbols: Sequence[str], start: date, end: date) -> tuple[pd.DataFrame | None, str]:
        stderr = io.StringIO()
        stdout = io.StringIO()
        frame: pd.DataFrame | None = None
        try:
            with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout):
                frame = yf.download(
                    tickers=list(symbols), start=start.isoformat(), end=end.isoformat(),
                    interval='1d', auto_adjust=False, group_by='ticker', threads=False,
                    progress=False, actions=False, timeout=self.timeout_seconds,
                    multi_level_index=True,
                )
            details = '\n'.join(value for value in (stdout.getvalue(), stderr.getvalue()) if value).strip()
            self._diagnostics.suppressed_log_lines += len([line for line in details.splitlines() if line.strip()])
            return frame, details
        except Exception as exc:
            details = '\n'.join(value for value in (stdout.getvalue(), stderr.getvalue(), f'{type(exc).__name__}: {exc}') if value).strip()
            self._diagnostics.suppressed_log_lines += len([line for line in details.splitlines() if line.strip()])
            return frame, details

    def _download_chunk(self, symbols: Sequence[str], start: date, end: date) -> dict[str, tuple[PriceBar, ...]]:
        last_frame: pd.DataFrame | None = None
        for attempt in range(1, self.max_retries + 2):
            self._diagnostics.requests += 1
            frame, details = self._download_once(symbols, start, end)
            last_frame = frame
            rate_limited = self._is_rate_limit(details)
            has_data = frame is not None and not frame.empty
            if has_data and not rate_limited:
                self._consecutive_rate_limits = 0
                try:
                    return {symbol: self._bars_for_symbol(frame, symbol) for symbol in symbols}
                finally:
                    del frame
                    gc.collect()
            if rate_limited:
                self._diagnostics.rate_limit_events += 1
                self._diagnostics.affected_symbols.update(symbols)
                self._diagnostics.last_error = 'Provider rate limit detected'
                self._consecutive_rate_limits += 1
                if self._consecutive_rate_limits >= self.circuit_breaker_threshold:
                    self._diagnostics.circuit_open_events += 1
                    self._diagnostics.status = 'COOLING_DOWN'
                    if self.circuit_breaker_cooldown_seconds:
                        self._sleep(self.circuit_breaker_cooldown_seconds)
                    self._consecutive_rate_limits = 0
            elif details:
                self._diagnostics.last_error = details.splitlines()[-1][:500]
            if attempt <= self.max_retries:
                self._diagnostics.retries += 1
                self._diagnostics.status = 'RATE_LIMITED' if rate_limited else 'RETRYING'
                delay = self._delay(attempt, rate_limited)
                if delay:
                    self._sleep(delay)
            else:
                self._diagnostics.status = 'DEGRADED'
        if last_frame is not None:
            del last_frame
        gc.collect()
        return {symbol: () for symbol in symbols}

    def fetch_batch(self, symbols: Sequence[str], start: date, end: date) -> dict[str, tuple[PriceBar, ...]]:
        selected = tuple(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
        output: dict[str, tuple[PriceBar, ...]] = {}
        for offset in range(0, len(selected), self.provider_chunk_size):
            chunk = selected[offset:offset + self.provider_chunk_size]
            output.update(self._download_chunk(chunk, start, end))
        if self._diagnostics.status in {'RETRYING', 'COOLING_DOWN', 'RATE_LIMITED'}:
            self._diagnostics.status = 'RECOVERED'
        elif self._diagnostics.rate_limit_events == 0:
            self._diagnostics.status = 'HEALTHY'
        return output

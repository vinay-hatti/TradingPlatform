from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
import random
import threading
import time
from typing import Iterable

try:
    from trading_ai.market.universe import SP500
except ModuleNotFoundError:
    SP500 = ()


@dataclass(frozen=True)
class MarketDownloadResult:
    symbol: str
    success: bool
    rows: int
    message: str
    cache_file: str = ""
    attempts: int = 1


class RequestPacer:
    def __init__(self, interval_seconds: float) -> None:
        if interval_seconds < 0:
            raise ValueError("interval_seconds cannot be negative")
        self.interval_seconds = interval_seconds
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        if self.interval_seconds == 0:
            return
        with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next_allowed - now)
            if delay:
                time.sleep(delay)
            self._next_allowed = time.monotonic() + self.interval_seconds


class MarketDownloader:
    def __init__(
        self,
        service: object | None = None,
        *,
        max_workers: int = 1,
        request_interval_seconds: float = 15.0,
        max_retries: int = 5,
        initial_backoff_seconds: float = 30.0,
        max_backoff_seconds: float = 300.0,
    ) -> None:
        if max_workers <= 0:
            raise ValueError("max_workers must be positive")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if service is None:
            from trading_ai.market.service import MarketService
            service = MarketService()
        self.service = service
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.initial_backoff_seconds = initial_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.pacer = RequestPacer(request_interval_seconds)

    @staticmethod
    def _message(exc: Exception) -> str:
        return f"{type(exc).__name__}: {exc}"

    @classmethod
    def _is_rate_limit_error(cls, exc: Exception) -> bool:
        message = cls._message(exc).lower()
        return any(x in message for x in ("429", "too many requests", "rate limit", "ratelimit"))

    @classmethod
    def _is_transient_error(cls, exc: Exception) -> bool:
        message = cls._message(exc).lower()
        return any(
            x in message
            for x in (
                "429", "too many requests", "rate limit", "maxretryerror",
                "connectionerror", "connection reset", "read timed out",
                "timeout", "temporarily unavailable", "502", "503", "504",
            )
        )

    def _backoff(self, retry_number: int, rate_limited: bool) -> float:
        delay = self.initial_backoff_seconds * (2 ** max(0, retry_number - 1))
        if rate_limited:
            delay = max(delay, 60.0)
        delay = min(delay, self.max_backoff_seconds)
        return delay + random.uniform(0.0, min(5.0, delay * 0.1))

    def _download_one(
        self,
        symbol: str,
        *,
        start: str | date | datetime | None,
        end: str | date | datetime | None,
        lookback_days: int,
        force_refresh: bool,
    ) -> MarketDownloadResult:
        total_attempts = self.max_retries + 1
        for attempt in range(1, total_attempts + 1):
            try:
                self.pacer.wait()
                outcome = self.service.save_history(
                    symbol,
                    start=start,
                    end=end,
                    lookback_days=lookback_days,
                    force_refresh=force_refresh,
                )
                return MarketDownloadResult(
                    symbol=symbol,
                    success=True,
                    rows=int(outcome["rows"]),
                    message="downloaded",
                    cache_file=str(outcome["cache_file"]),
                    attempts=attempt,
                )
            except Exception as exc:
                if not self._is_transient_error(exc) or attempt >= total_attempts:
                    return MarketDownloadResult(
                        symbol=symbol,
                        success=False,
                        rows=0,
                        message=self._message(exc),
                        attempts=attempt,
                    )
                delay = self._backoff(attempt, self._is_rate_limit_error(exc))
                print(
                    f"[RETRY] {symbol}: attempt {attempt}/{total_attempts} failed "
                    f"({type(exc).__name__}); sleeping {delay:.1f}s."
                )
                time.sleep(delay)
        raise AssertionError("unreachable")

    def run_bulk_download(
        self,
        *,
        symbols: Iterable[str] | None = None,
        start: str | date | datetime | None = None,
        end: str | date | datetime | None = None,
        lookback_days: int = 730,
        force_refresh: bool = False,
        fail_on_error: bool = True,
    ) -> tuple[MarketDownloadResult, ...]:
        selected = tuple(
            dict.fromkeys(
                symbol.upper().strip()
                for symbol in (symbols or SP500)
                if symbol and symbol.strip()
            )
        )
        if not selected:
            raise ValueError("At least one symbol is required")

        results: list[MarketDownloadResult] = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(selected))) as executor:
            futures = {
                executor.submit(
                    self._download_one,
                    symbol,
                    start=start,
                    end=end,
                    lookback_days=lookback_days,
                    force_refresh=force_refresh,
                ): symbol
                for symbol in selected
            }
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                status = "OK" if result.success else "FAILED"
                print(
                    f"[{status}] {result.symbol}: {result.rows} rows; "
                    f"attempts={result.attempts}; {result.message}"
                )

        ordered = tuple(sorted(results, key=lambda item: selected.index(item.symbol)))
        failures = tuple(item for item in ordered if not item.success)
        if failures and fail_on_error:
            details = "; ".join(f"{item.symbol}: {item.message}" for item in failures)
            raise RuntimeError(
                f"Market ingestion failed for {len(failures)} of "
                f"{len(ordered)} symbols: {details}"
            )
        return ordered

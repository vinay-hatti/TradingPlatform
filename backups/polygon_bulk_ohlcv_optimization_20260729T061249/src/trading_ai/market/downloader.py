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
    downloaded_rows: int = 0
    persisted_rows: int = 0
    inserted_rows: int = 0
    updated_rows: int = 0
    provider: str = ""
    error_category: str = ""


class RequestPacer:
    """Globally serialize requests and coordinate 429 cooldowns across workers."""

    def __init__(
        self,
        interval_seconds: float,
        *,
        rate_limit_floor_seconds: float = 15.0,
    ) -> None:
        if interval_seconds < 0:
            raise ValueError("interval_seconds cannot be negative")
        if rate_limit_floor_seconds < 0:
            raise ValueError("rate_limit_floor_seconds cannot be negative")
        self.base_interval_seconds = float(interval_seconds)
        self.rate_limit_floor_seconds = float(rate_limit_floor_seconds)
        self._effective_interval_seconds = float(interval_seconds)
        self._lock = threading.Lock()
        self._next_allowed = 0.0
        self._cooldown_until = 0.0
        self._rate_limit_events = 0

    @property
    def effective_interval_seconds(self) -> float:
        with self._lock:
            return self._effective_interval_seconds

    @property
    def rate_limit_events(self) -> int:
        with self._lock:
            return self._rate_limit_events

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            target = max(self._next_allowed, self._cooldown_until)
            delay = max(0.0, target - now)
            if delay:
                time.sleep(delay)
            self._next_allowed = (
                time.monotonic() + self._effective_interval_seconds
            )

    def register_rate_limit(self, cooldown_seconds: float) -> dict[str, float | int]:
        """Apply one process-wide cooldown and reduce request rate for the run."""
        with self._lock:
            self._rate_limit_events += 1
            multiplier = 2 ** max(0, self._rate_limit_events - 1)
            adaptive_interval = self.rate_limit_floor_seconds * multiplier
            self._effective_interval_seconds = max(
                self._effective_interval_seconds,
                adaptive_interval,
            )
            now = time.monotonic()
            self._cooldown_until = max(
                self._cooldown_until,
                now + max(0.0, cooldown_seconds),
            )
            self._next_allowed = max(
                self._next_allowed,
                self._cooldown_until,
            )
            return {
                "events": self._rate_limit_events,
                "effective_interval_seconds": self._effective_interval_seconds,
                "cooldown_seconds": max(0.0, self._cooldown_until - now),
            }


class MarketDownloader:
    def __init__(
        self,
        service: object | None = None,
        *,
        max_workers: int = 1,
        request_interval_seconds: float = 15.0,
        max_retries: int = 5,
        initial_backoff_seconds: float = 30.0,
        network_backoff_seconds: float = 5.0,
        max_backoff_seconds: float = 300.0,
        rate_limit_floor_seconds: float = 15.0,
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
        if initial_backoff_seconds < 0:
            raise ValueError("initial_backoff_seconds cannot be negative")
        if network_backoff_seconds < 0:
            raise ValueError("network_backoff_seconds cannot be negative")
        if max_backoff_seconds < 0:
            raise ValueError("max_backoff_seconds cannot be negative")
        self.initial_backoff_seconds = initial_backoff_seconds
        self.network_backoff_seconds = network_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.pacer = RequestPacer(
            request_interval_seconds,
            rate_limit_floor_seconds=rate_limit_floor_seconds,
        )

    @staticmethod
    def _exception_chain(exc: BaseException) -> tuple[BaseException, ...]:
        chain: list[BaseException] = []
        seen: set[int] = set()
        current: BaseException | None = exc
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            chain.append(current)
            current = current.__cause__ or current.__context__
        return tuple(chain)

    @classmethod
    def _message(cls, exc: Exception) -> str:
        parts = []
        for item in cls._exception_chain(exc):
            text = str(item).strip()
            rendered = type(item).__name__ + (f": {text}" if text else "")
            if rendered not in parts:
                parts.append(rendered)
        return " <- ".join(parts)

    @classmethod
    def _classify_error(cls, exc: Exception) -> str:
        message = cls._message(exc).lower()
        if any(token in message for token in (
            "429", "too many requests", "rate limit", "ratelimit",
        )):
            return "RATE_LIMIT"
        if any(token in message for token in (
            "401", "403", "unauthorized", "forbidden", "api key", "auth",
        )):
            return "AUTH"
        if any(token in message for token in (
            "500", "502", "503", "504", "bad gateway",
            "service unavailable", "gateway timeout",
        )):
            return "SERVER"
        if any(token in message for token in (
            "name resolution", "nodename nor servname", "dns",
            "connection refused", "connection reset", "remote disconnected",
            "broken pipe", "network is unreachable", "newconnectionerror",
            "protocolerror", "sslerror", "certificate",
        )):
            return "CONNECTION"
        if any(token in message for token in (
            "read timed out", "connect timeout", "timeout", "timed out",
        )):
            return "TIMEOUT"
        if "maxretryerror" in message:
            return "TRANSPORT"
        return "PERMANENT"

    @classmethod
    def _is_transient_error(cls, exc: Exception) -> bool:
        return cls._classify_error(exc) in {
            "RATE_LIMIT", "SERVER", "CONNECTION", "TIMEOUT", "TRANSPORT"
        }

    def _backoff(self, retry_number: int, category: str) -> float:
        if category == "RATE_LIMIT":
            base = max(self.initial_backoff_seconds, 60.0)
        elif category in {"CONNECTION", "TIMEOUT", "TRANSPORT"}:
            base = self.network_backoff_seconds
        else:
            base = self.initial_backoff_seconds
        delay = base * (2 ** max(0, retry_number - 1))
        delay = min(delay, self.max_backoff_seconds)
        return delay + random.uniform(0.0, min(5.0, max(0.1, delay * 0.1)))

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
                downloaded = int(outcome.get("downloaded_rows", outcome.get("rows", 0)))
                persisted = int(outcome.get("persisted_rows", outcome.get("rows", 0)))
                return MarketDownloadResult(
                    symbol=symbol,
                    success=True,
                    rows=persisted,
                    message="downloaded_and_persisted",
                    cache_file=str(outcome["cache_file"]),
                    attempts=attempt,
                    downloaded_rows=downloaded,
                    persisted_rows=persisted,
                    inserted_rows=int(outcome.get("inserted_rows", 0)),
                    updated_rows=int(outcome.get("updated_rows", 0)),
                    provider=str(outcome.get("provider", "")),
                )
            except Exception as exc:
                if not self._is_transient_error(exc) or attempt >= total_attempts:
                    return MarketDownloadResult(
                        symbol=symbol,
                        success=False,
                        rows=0,
                        message=self._message(exc),
                        attempts=attempt,
                        error_category=self._classify_error(exc),
                    )
                category = self._classify_error(exc)
                delay = self._backoff(attempt, category)
                if category == "RATE_LIMIT":
                    state = self.pacer.register_rate_limit(delay)
                    print(
                        f"[RETRY] {symbol}: attempt {attempt}/{total_attempts} failed; "
                        f"category={category}; cause={self._message(exc)}; "
                        f"global_cooldown={state['cooldown_seconds']:.1f}s; "
                        f"effective_interval="
                        f"{state['effective_interval_seconds']:.1f}s; "
                        f"rate_limit_events={state['events']}."
                    )
                else:
                    print(
                        f"[RETRY] {symbol}: attempt {attempt}/{total_attempts} failed; "
                        f"category={category}; cause={self._message(exc)}; "
                        f"sleeping {delay:.1f}s."
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
                if result.success:
                    print(
                        f"[OK] {result.symbol}: {result.downloaded_rows} downloaded; "
                        f"{result.persisted_rows} persisted "
                        f"({result.inserted_rows} inserted, {result.updated_rows} updated); "
                        f"provider={result.provider}; attempts={result.attempts}"
                    )
                else:
                    print(
                        f"[FAILED] {result.symbol}: 0 persisted; "
                        f"attempts={result.attempts}; "
                        f"category={result.error_category}; {result.message}"
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

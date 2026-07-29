from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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
    def __init__(self, interval_seconds: float, *, rate_limit_floor_seconds: float = 15.0) -> None:
        if interval_seconds < 0 or rate_limit_floor_seconds < 0:
            raise ValueError("request pacing values cannot be negative")
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

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            target = max(self._next_allowed, self._cooldown_until)
            delay = max(0.0, target - now)
            if delay:
                time.sleep(delay)
            self._next_allowed = time.monotonic() + self._effective_interval_seconds

    def register_rate_limit(self, cooldown_seconds: float) -> dict[str, float | int]:
        with self._lock:
            self._rate_limit_events += 1
            adaptive = self.rate_limit_floor_seconds * (2 ** max(0, self._rate_limit_events - 1))
            self._effective_interval_seconds = max(self._effective_interval_seconds, adaptive)
            now = time.monotonic()
            self._cooldown_until = max(self._cooldown_until, now + max(0.0, cooldown_seconds))
            self._next_allowed = max(self._next_allowed, self._cooldown_until)
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
        fetch_mode: str = "auto",
        incremental_sessions: int = 3,
        stale_threshold_days: int = 10,
    ) -> None:
        if max_workers <= 0 or max_retries < 0:
            raise ValueError("invalid downloader worker/retry configuration")
        if fetch_mode not in {"auto", "grouped", "per-symbol"}:
            raise ValueError("fetch_mode must be auto, grouped, or per-symbol")
        if incremental_sessions <= 0 or stale_threshold_days <= 0:
            raise ValueError("incremental session/staleness values must be positive")
        if service is None:
            from trading_ai.market.service import MarketService
            service = MarketService()
        self.service = service
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.initial_backoff_seconds = float(initial_backoff_seconds)
        self.network_backoff_seconds = float(network_backoff_seconds)
        self.max_backoff_seconds = float(max_backoff_seconds)
        self.fetch_mode = fetch_mode
        self.incremental_sessions = incremental_sessions
        self.stale_threshold_days = stale_threshold_days
        self.pacer = RequestPacer(request_interval_seconds, rate_limit_floor_seconds=rate_limit_floor_seconds)

    @staticmethod
    def _exception_chain(exc: BaseException) -> tuple[BaseException, ...]:
        chain, seen = [], set()
        current: BaseException | None = exc
        while current is not None and id(current) not in seen:
            seen.add(id(current)); chain.append(current)
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
        if any(x in message for x in ("429", "too many requests", "rate limit", "ratelimit")): return "RATE_LIMIT"
        if any(x in message for x in ("401", "403", "unauthorized", "forbidden", "api key", "auth")): return "AUTH"
        if any(x in message for x in ("500", "502", "503", "504", "bad gateway", "service unavailable")): return "SERVER"
        if any(x in message for x in ("name resolution", "dns", "connection refused", "connection reset", "remote disconnected", "newconnectionerror", "protocolerror", "sslerror")): return "CONNECTION"
        if any(x in message for x in ("read timed out", "connect timeout", "timeout", "timed out")): return "TIMEOUT"
        if "maxretryerror" in message: return "TRANSPORT"
        return "PERMANENT"

    @classmethod
    def _is_transient_error(cls, exc: Exception) -> bool:
        return cls._classify_error(exc) in {"RATE_LIMIT", "SERVER", "CONNECTION", "TIMEOUT", "TRANSPORT"}

    def _backoff(self, retry_number: int, category: str) -> float:
        base = max(self.initial_backoff_seconds, 60.0) if category == "RATE_LIMIT" else (
            self.network_backoff_seconds if category in {"CONNECTION", "TIMEOUT", "TRANSPORT"} else self.initial_backoff_seconds
        )
        delay = min(base * (2 ** max(0, retry_number - 1)), self.max_backoff_seconds)
        return delay + random.uniform(0.0, min(5.0, max(0.1, delay * 0.1)))

    def _call_with_retry(self, label: str, operation):
        total_attempts = self.max_retries + 1
        for attempt in range(1, total_attempts + 1):
            try:
                self.pacer.wait()
                return operation(), attempt
            except Exception as exc:
                category = self._classify_error(exc)
                if not self._is_transient_error(exc) or attempt >= total_attempts:
                    raise
                delay = self._backoff(attempt, category)
                if category == "RATE_LIMIT":
                    state = self.pacer.register_rate_limit(delay)
                    print(
                        f"[RETRY] {label}: attempt {attempt}/{total_attempts} failed; category={category}; "
                        f"global_cooldown={state['cooldown_seconds']:.1f}s; "
                        f"effective_interval={state['effective_interval_seconds']:.1f}s; cause={self._message(exc)}"
                    )
                else:
                    print(f"[RETRY] {label}: attempt {attempt}/{total_attempts} failed; category={category}; sleeping {delay:.1f}s; cause={self._message(exc)}")
                    time.sleep(delay)
        raise AssertionError("unreachable")

    @staticmethod
    def _date_range(start: date, end: date) -> list[date]:
        values = []
        current = start
        while current <= end:
            if current.weekday() < 5:
                values.append(current)
            current += timedelta(days=1)
        return values

    def _download_one(self, symbol: str, *, start, end, lookback_days: int, force_refresh: bool) -> MarketDownloadResult:
        try:
            outcome, attempts = self._call_with_retry(
                symbol,
                lambda: self.service.save_history(symbol, start=start, end=end, lookback_days=lookback_days, force_refresh=force_refresh),
            )
            return MarketDownloadResult(
                symbol=symbol, success=True, rows=int(outcome.get("persisted_rows", 0)),
                message="downloaded_and_persisted", cache_file=str(outcome.get("cache_file", "")), attempts=attempts,
                downloaded_rows=int(outcome.get("downloaded_rows", 0)), persisted_rows=int(outcome.get("persisted_rows", 0)),
                inserted_rows=int(outcome.get("inserted_rows", 0)), updated_rows=int(outcome.get("updated_rows", 0)),
                provider=str(outcome.get("provider", "")),
            )
        except Exception as exc:
            return MarketDownloadResult(symbol=symbol, success=False, rows=0, message=self._message(exc), attempts=self.max_retries + 1, error_category=self._classify_error(exc))

    def _run_per_symbol(self, selected, *, start, end, lookback_days, force_refresh):
        results = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(selected))) as executor:
            futures = {executor.submit(self._download_one, symbol, start=start, end=end, lookback_days=lookback_days, force_refresh=force_refresh): symbol for symbol in selected}
            for future in as_completed(futures):
                result = future.result(); results.append(result)
                if result.success:
                    print(f"[OK] {result.symbol}: {result.downloaded_rows} downloaded; {result.persisted_rows} persisted ({result.inserted_rows} inserted, {result.updated_rows} updated); provider={result.provider}; attempts={result.attempts}")
                else:
                    print(f"[FAILED] {result.symbol}: category={result.error_category}; {result.message}")
        return results

    def _run_grouped(self, selected, *, start, end, lookback_days, force_refresh, repair_stale: bool):
        end_date = date.today() if end is None else date.fromisoformat(str(end)[:10])
        start_date = end_date - timedelta(days=lookback_days) if start is None else date.fromisoformat(str(start)[:10])
        all_dates = self._date_range(start_date, end_date)
        latest = self.service.latest_dates(selected)
        stale_cutoff = end_date - timedelta(days=self.stale_threshold_days)
        stale = tuple(symbol for symbol in selected if latest.get(symbol) is None or latest[symbol] < stale_cutoff)

        if force_refresh:
            grouped_dates = all_dates
        else:
            grouped_dates = all_dates[-self.incremental_sessions:]

        counters = {symbol: {"downloaded": 0, "persisted": 0, "inserted": 0, "updated": 0} for symbol in selected}
        failed_dates = []
        print(
            f"Polygon grouped daily mode: requests={len(grouped_dates)} instead of {len(selected)} ticker requests; "
            f"incremental_sessions={self.incremental_sessions}; stale_repairs={len(stale) if repair_stale and not force_refresh else 0}; cache_write=false"
        )
        for position, trading_date in enumerate(grouped_dates, start=1):
            try:
                outcome, attempts = self._call_with_retry(
                    f"GROUPED {trading_date.isoformat()}",
                    lambda d=trading_date: self.service.save_grouped_daily(selected, d),
                )
                present = outcome.get("symbols_with_bars", {})
                for symbol, count in present.items():
                    counters[symbol]["downloaded"] += int(count)
                    counters[symbol]["persisted"] += int(count)
                print(
                    f"[BULK OK] {trading_date}: {outcome['downloaded_rows']} canonical bars; "
                    f"{outcome['persisted_rows']} persisted ({outcome['inserted_rows']} inserted, {outcome['updated_rows']} updated); "
                    f"request={position}/{len(grouped_dates)}; attempts={attempts}"
                )
            except Exception as exc:
                failed_dates.append((trading_date, exc))
                print(f"[BULK FAILED] {trading_date}: category={self._classify_error(exc)}; {self._message(exc)}")

        repairs = []
        if repair_stale and stale and not force_refresh:
            print(f"Repairing {len(stale)} stale/missing symbols with ticker-specific historical requests.")
            repairs = self._run_per_symbol(stale, start=start, end=end, lookback_days=lookback_days, force_refresh=True)
            repair_map = {result.symbol: result for result in repairs}
        else:
            repair_map = {}

        results = []
        for symbol in selected:
            repair = repair_map.get(symbol)
            c = counters[symbol]
            success = not failed_dates and (repair is None or repair.success)
            results.append(MarketDownloadResult(
                symbol=symbol,
                success=success,
                rows=c["persisted"] + (repair.persisted_rows if repair else 0),
                message="grouped_daily_persisted" if success else (repair.message if repair and not repair.success else "one_or_more_grouped_dates_failed"),
                attempts=1,
                downloaded_rows=c["downloaded"] + (repair.downloaded_rows if repair else 0),
                persisted_rows=c["persisted"] + (repair.persisted_rows if repair else 0),
                inserted_rows=(repair.inserted_rows if repair else 0),
                updated_rows=(repair.updated_rows if repair else 0),
                provider=type(self.service.provider).__name__,
                error_category=(repair.error_category if repair and not repair.success else ("BULK_DATE" if failed_dates else "")),
            ))
        return results

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
        selected = tuple(dict.fromkeys(symbol.upper().strip() for symbol in (symbols or SP500) if symbol and symbol.strip()))
        if not selected:
            raise ValueError("At least one symbol is required")
        supports_grouped = hasattr(self.service, "save_grouped_daily") and hasattr(self.service.provider, "fetch_grouped_daily")
        use_grouped = supports_grouped and self.fetch_mode in {"auto", "grouped"}
        if use_grouped:
            results = self._run_grouped(selected, start=start, end=end, lookback_days=lookback_days, force_refresh=force_refresh, repair_stale=self.fetch_mode == "auto")
        else:
            results = self._run_per_symbol(selected, start=start, end=end, lookback_days=lookback_days, force_refresh=force_refresh)
        ordered = tuple(sorted(results, key=lambda item: selected.index(item.symbol)))
        failures = tuple(item for item in ordered if not item.success)
        if failures and fail_on_error:
            raise RuntimeError(f"Market ingestion failed for {len(failures)} of {len(ordered)} symbols")
        return ordered

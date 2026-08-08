from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Mapping, Sequence

from trading_ai.market.providers.polygon import PolygonHistoricalProvider

from .models import PriceBar


@dataclass
class ProviderDiagnostics:
    provider: str = "POLYGON"
    status: str = "HEALTHY"
    requests: int = 0
    retries: int = 0
    rate_limit_events: int = 0
    circuit_open_events: int = 0
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
            "affected_symbols": sorted(self.affected_symbols),
            "last_error": self.last_error,
        }


class PolygonBulkHistoricalProvider:
    """Bounded Polygon OHLCV provider compatible with the bulk population pipeline.

    The historical population service uses an exclusive ``end`` boundary. Polygon's
    aggregates endpoint is inclusive, so this adapter subtracts one day before
    delegating to :class:`PolygonHistoricalProvider`.
    """

    def __init__(
        self,
        *,
        provider_tickers: Mapping[str, str] | None = None,
        api_key: str | None = None,
        historical_provider: PolygonHistoricalProvider | None = None,
        max_retries: int = 3,
        initial_backoff_seconds: float = 2.0,
        max_backoff_seconds: float = 60.0,
        jitter_ratio: float = 0.20,
        rate_limit_cooldown_seconds: float = 15.0,
        circuit_breaker_threshold: int = 3,
        circuit_breaker_cooldown_seconds: float = 30.0,
        request_pause_seconds: float = 0.0,
        sleep: Callable[[float], None] = time.sleep,
        random_value: Callable[[], float] = random.random,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if initial_backoff_seconds < 0 or max_backoff_seconds < 0:
            raise ValueError("backoff values cannot be negative")
        if max_backoff_seconds < initial_backoff_seconds:
            raise ValueError("max_backoff_seconds cannot be below initial_backoff_seconds")
        if not 0 <= jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between 0 and 1")
        if circuit_breaker_threshold < 1:
            raise ValueError("circuit_breaker_threshold must be positive")
        if request_pause_seconds < 0:
            raise ValueError("request_pause_seconds cannot be negative")

        self.historical_provider = historical_provider or PolygonHistoricalProvider(
            provider_tickers=provider_tickers,
            api_key=api_key,
        )
        self.max_retries = int(max_retries)
        self.initial_backoff_seconds = float(initial_backoff_seconds)
        self.max_backoff_seconds = float(max_backoff_seconds)
        self.jitter_ratio = float(jitter_ratio)
        self.rate_limit_cooldown_seconds = float(rate_limit_cooldown_seconds)
        self.circuit_breaker_threshold = int(circuit_breaker_threshold)
        self.circuit_breaker_cooldown_seconds = float(circuit_breaker_cooldown_seconds)
        self.request_pause_seconds = float(request_pause_seconds)
        self._sleep = sleep
        self._random = random_value
        self._consecutive_rate_limits = 0
        self._diagnostics = ProviderDiagnostics()

    @property
    def name(self) -> str:
        return "POLYGON"

    @staticmethod
    def _is_rate_limit(message: str) -> bool:
        value = message.lower()
        return any(token in value for token in ("429", "too many requests", "rate limit", "ratelimit"))

    def _delay(self, retry_number: int, rate_limited: bool) -> float:
        base = self.initial_backoff_seconds * (2 ** max(0, retry_number - 1))
        if rate_limited:
            base = max(base, self.rate_limit_cooldown_seconds)
        capped = min(base, self.max_backoff_seconds)
        return capped + capped * self.jitter_ratio * self._random()

    def diagnostics(self) -> dict:
        return self._diagnostics.to_dict()

    @staticmethod
    def _to_price_bar(bar) -> PriceBar:
        timestamp = datetime.fromtimestamp(int(bar.time) / 1000.0, tz=timezone.utc)
        return PriceBar(
            symbol=str(bar.symbol).strip().upper(),
            date=timestamp.date(),
            open=float(bar.open),
            high=float(bar.high),
            low=float(bar.low),
            close=float(bar.close),
            volume=float(bar.volume or 0.0),
        )

    def _fetch_symbol(self, symbol: str, start: date, end: date) -> tuple[PriceBar, ...]:
        inclusive_end = end - timedelta(days=1)
        if inclusive_end < start:
            return ()
        for attempt in range(1, self.max_retries + 2):
            self._diagnostics.requests += 1
            try:
                bars = self.historical_provider.fetch_history(
                    symbol,
                    start.isoformat(),
                    inclusive_end.isoformat(),
                )
                self._consecutive_rate_limits = 0
                return tuple(self._to_price_bar(bar) for bar in bars)
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                rate_limited = self._is_rate_limit(message)
                self._diagnostics.last_error = message[:500]
                self._diagnostics.affected_symbols.add(symbol)
                if rate_limited:
                    self._diagnostics.rate_limit_events += 1
                    self._consecutive_rate_limits += 1
                    if self._consecutive_rate_limits >= self.circuit_breaker_threshold:
                        self._diagnostics.circuit_open_events += 1
                        self._diagnostics.status = "COOLING_DOWN"
                        if self.circuit_breaker_cooldown_seconds:
                            self._sleep(self.circuit_breaker_cooldown_seconds)
                        self._consecutive_rate_limits = 0
                if attempt > self.max_retries:
                    self._diagnostics.status = "DEGRADED"
                    return ()
                self._diagnostics.retries += 1
                self._diagnostics.status = "RATE_LIMITED" if rate_limited else "RETRYING"
                delay = self._delay(attempt, rate_limited)
                if delay:
                    self._sleep(delay)
        return ()

    def fetch_batch(
        self,
        symbols: Sequence[str],
        start: date,
        end: date,
    ) -> dict[str, tuple[PriceBar, ...]]:
        selected = tuple(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
        output: dict[str, tuple[PriceBar, ...]] = {}
        for index, symbol in enumerate(selected):
            output[symbol] = self._fetch_symbol(symbol, start, end)
            if self.request_pause_seconds and index + 1 < len(selected):
                self._sleep(self.request_pause_seconds)
        if self._diagnostics.status in {"RETRYING", "COOLING_DOWN", "RATE_LIMITED"}:
            self._diagnostics.status = "RECOVERED"
        elif self._diagnostics.rate_limit_events == 0 and not self._diagnostics.last_error:
            self._diagnostics.status = "HEALTHY"
        return output

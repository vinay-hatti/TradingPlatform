from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Protocol

from .contracts import CoverageStatus, SymbolCoverageProfile, UniverseCoverageProfile


class TradingCalendar(Protocol):
    def is_trading_day(self, value: date) -> bool: ...
    def previous_trading_day(self, value: date) -> date: ...


@dataclass(frozen=True, slots=True)
class WeekdayTradingCalendar:
    """Dependency-free weekday calendar used until exchange-holiday integration."""

    holidays: frozenset[date] = frozenset()

    def is_trading_day(self, value: date) -> bool:
        return value.weekday() < 5 and value not in self.holidays

    def previous_trading_day(self, value: date) -> date:
        candidate = value
        while not self.is_trading_day(candidate):
            candidate -= timedelta(days=1)
        return candidate


@dataclass(frozen=True, slots=True)
class MarketDataFreshnessPolicy:
    ready_staleness_days: int = 0
    degraded_staleness_days: int = 1
    review_staleness_days: int = 3
    ready_fresh_percentage: float = 99.0
    degraded_fresh_percentage: float = 95.0
    review_fresh_percentage: float = 80.0

    def __post_init__(self) -> None:
        if not (0 <= self.ready_staleness_days <= self.degraded_staleness_days <= self.review_staleness_days):
            raise ValueError("staleness thresholds must be monotonically increasing")
        thresholds = (
            self.ready_fresh_percentage,
            self.degraded_fresh_percentage,
            self.review_fresh_percentage,
        )
        if any(value < 0.0 or value > 100.0 for value in thresholds):
            raise ValueError("freshness percentages must be between 0 and 100")
        if not (
            self.ready_fresh_percentage
            >= self.degraded_fresh_percentage
            >= self.review_fresh_percentage
        ):
            raise ValueError("freshness percentages must be monotonically decreasing")

    def classify_staleness(self, staleness_days: int | None) -> tuple[CoverageStatus, tuple[str, ...]]:
        if staleness_days is None:
            return CoverageStatus.FAILED, ("NO_PRICE_HISTORY",)
        if staleness_days <= self.ready_staleness_days:
            return CoverageStatus.READY, ()
        if staleness_days <= self.degraded_staleness_days:
            return CoverageStatus.DEGRADED, (f"STALE_BY_{staleness_days}_TRADING_DAYS",)
        if staleness_days <= self.review_staleness_days:
            return CoverageStatus.REVIEW, (f"STALE_BY_{staleness_days}_TRADING_DAYS",)
        return CoverageStatus.FAILED, (f"STALE_BY_{staleness_days}_TRADING_DAYS",)


@dataclass(frozen=True, slots=True)
class SymbolFreshnessProfile:
    symbol: str
    latest_bar_date: date | None
    expected_latest_trading_date: date
    staleness_days: int | None
    is_stale: bool
    status: CoverageStatus
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        normalized = self.symbol.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be blank")
        if self.staleness_days is not None and self.staleness_days < 0:
            raise ValueError("staleness_days must be non-negative")
        object.__setattr__(self, "symbol", normalized)
        object.__setattr__(self, "reasons", tuple(self.reasons))


@dataclass(frozen=True, slots=True)
class UniverseFreshnessProfile:
    canonical_symbol_count: int
    symbols_with_history: int
    fresh_symbol_count: int
    stale_symbol_count: int
    missing_symbol_count: int
    fresh_percentage: float
    expected_latest_trading_date: date
    status: CoverageStatus
    symbol_profiles: tuple[SymbolFreshnessProfile, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        counts = (
            self.canonical_symbol_count,
            self.symbols_with_history,
            self.fresh_symbol_count,
            self.stale_symbol_count,
            self.missing_symbol_count,
        )
        if any(value < 0 for value in counts):
            raise ValueError("freshness counts must be non-negative")
        if self.symbols_with_history + self.missing_symbol_count != self.canonical_symbol_count:
            raise ValueError("history and missing counts must equal canonical_symbol_count")
        if self.fresh_symbol_count + self.stale_symbol_count != self.symbols_with_history:
            raise ValueError("fresh and stale counts must equal symbols_with_history")
        if not 0.0 <= self.fresh_percentage <= 100.0:
            raise ValueError("fresh_percentage must be between 0 and 100")
        object.__setattr__(self, "symbol_profiles", tuple(self.symbol_profiles))
        object.__setattr__(self, "reasons", tuple(self.reasons))


class MarketDataFreshnessEngine:
    def __init__(
        self,
        policy: MarketDataFreshnessPolicy | None = None,
        calendar: TradingCalendar | None = None,
    ) -> None:
        self.policy = policy or MarketDataFreshnessPolicy()
        self.calendar = calendar or WeekdayTradingCalendar()

    def expected_latest_trading_date(self, as_of_date: date) -> date:
        return self.calendar.previous_trading_day(as_of_date)

    def trading_day_distance(self, latest: date, expected: date) -> int:
        if latest >= expected:
            return 0
        count = 0
        cursor = latest + timedelta(days=1)
        while cursor <= expected:
            if self.calendar.is_trading_day(cursor):
                count += 1
            cursor += timedelta(days=1)
        return count

    def evaluate_symbol(
        self,
        profile: SymbolCoverageProfile,
        *,
        expected_latest_trading_date: date,
    ) -> SymbolFreshnessProfile:
        latest = profile.latest_date
        distance = None if latest is None else self.trading_day_distance(latest, expected_latest_trading_date)
        status, reasons = self.policy.classify_staleness(distance)
        return SymbolFreshnessProfile(
            symbol=profile.symbol,
            latest_bar_date=latest,
            expected_latest_trading_date=expected_latest_trading_date,
            staleness_days=distance,
            is_stale=(distance is None or distance > self.policy.ready_staleness_days),
            status=status,
            reasons=reasons,
        )

    def evaluate(
        self,
        coverage: UniverseCoverageProfile,
        *,
        as_of_date: date | None = None,
    ) -> UniverseFreshnessProfile:
        as_of = as_of_date or datetime.now(timezone.utc).date()
        expected = self.expected_latest_trading_date(as_of)
        symbols = tuple(
            self.evaluate_symbol(item, expected_latest_trading_date=expected)
            for item in coverage.symbol_profiles
        )
        with_history = sum(1 for item in symbols if item.latest_bar_date is not None)
        missing = len(symbols) - with_history
        fresh = sum(1 for item in symbols if item.status is CoverageStatus.READY)
        stale = with_history - fresh
        denominator = len(symbols) or 1
        fresh_percentage = round(fresh * 100.0 / denominator, 4)
        reasons: list[str] = []

        if not symbols:
            status = CoverageStatus.FAILED
            reasons.append("EMPTY_CANONICAL_UNIVERSE")
        elif fresh_percentage < self.policy.review_fresh_percentage:
            status = CoverageStatus.FAILED
            reasons.append("FRESHNESS_BELOW_REVIEW_THRESHOLD")
        elif fresh_percentage < self.policy.degraded_fresh_percentage:
            status = CoverageStatus.REVIEW
            reasons.append("FRESHNESS_REQUIRES_REVIEW")
        elif fresh_percentage < self.policy.ready_fresh_percentage:
            status = CoverageStatus.DEGRADED
            reasons.append("FRESHNESS_BELOW_READY_THRESHOLD")
        else:
            status = CoverageStatus.READY

        return UniverseFreshnessProfile(
            canonical_symbol_count=len(symbols),
            symbols_with_history=with_history,
            fresh_symbol_count=fresh,
            stale_symbol_count=stale,
            missing_symbol_count=missing,
            fresh_percentage=fresh_percentage,
            expected_latest_trading_date=expected,
            status=status,
            symbol_profiles=symbols,
            reasons=reasons,
        )

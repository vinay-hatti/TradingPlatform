from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Iterable, Mapping, Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


class CompletenessStatus(str, Enum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    REVIEW = "REVIEW"
    FAILED = "FAILED"


@dataclass(frozen=True)
class MarketDataCompletenessPolicy:
    lookback_trading_days: int = 252
    ready_continuity_percentage: float = 99.0
    degraded_continuity_percentage: float = 97.0
    review_continuity_percentage: float = 90.0
    maximum_ready_duplicate_rows: int = 0
    maximum_degraded_duplicate_rows: int = 1
    maximum_ready_non_trading_rows: int = 0
    maximum_degraded_non_trading_rows: int = 1

    def validate(self) -> None:
        if self.lookback_trading_days < 1:
            raise ValueError("lookback_trading_days must be positive")
        thresholds = (
            self.ready_continuity_percentage,
            self.degraded_continuity_percentage,
            self.review_continuity_percentage,
        )
        if not all(0.0 <= value <= 100.0 for value in thresholds):
            raise ValueError("continuity thresholds must be between 0 and 100")
        if not (
            self.ready_continuity_percentage
            >= self.degraded_continuity_percentage
            >= self.review_continuity_percentage
        ):
            raise ValueError("continuity thresholds must be descending")


@dataclass(frozen=True)
class SymbolCompletenessProfile:
    symbol: str
    window_start: date
    window_end: date
    expected_trading_days: int
    observed_trading_days: int
    missing_trading_days: tuple[date, ...] = ()
    duplicate_row_count: int = 0
    weekend_row_dates: tuple[date, ...] = ()
    holiday_row_dates: tuple[date, ...] = ()
    continuity_percentage: float = 0.0
    status: CompletenessStatus = CompletenessStatus.FAILED
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class UniverseCompletenessProfile:
    as_of_date: date
    canonical_symbol_count: int
    evaluated_symbol_count: int
    ready_symbol_count: int
    degraded_symbol_count: int
    review_symbol_count: int
    failed_symbol_count: int
    symbols_with_missing_days: int
    total_missing_trading_days: int
    symbols_with_duplicates: int
    total_duplicate_rows: int
    symbols_with_non_trading_rows: int
    average_continuity_percentage: float
    minimum_continuity_percentage: float
    status: CompletenessStatus
    symbol_profiles: tuple[SymbolCompletenessProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)


class WeekdayTradingCalendar:
    """Deterministic weekday calendar with optional exchange-holiday overrides."""

    def __init__(self, holidays: Iterable[date] = ()) -> None:
        self._holidays = frozenset(holidays)

    @property
    def holidays(self) -> frozenset[date]:
        return self._holidays

    def is_trading_day(self, value: date) -> bool:
        return value.weekday() < 5 and value not in self._holidays

    def trading_days(self, start: date, end: date) -> tuple[date, ...]:
        if end < start:
            return ()
        result: list[date] = []
        current = start
        while current <= end:
            if self.is_trading_day(current):
                result.append(current)
            current += timedelta(days=1)
        return tuple(result)

    def previous_trading_days(self, end: date, count: int) -> tuple[date, ...]:
        if count < 1:
            return ()
        result: list[date] = []
        current = end
        while len(result) < count:
            if self.is_trading_day(current):
                result.append(current)
            current -= timedelta(days=1)
        result.reverse()
        return tuple(result)


class MarketDataCompletenessEngine:
    def __init__(
        self,
        policy: MarketDataCompletenessPolicy | None = None,
        calendar: WeekdayTradingCalendar | None = None,
    ) -> None:
        self.policy = policy or MarketDataCompletenessPolicy()
        self.policy.validate()
        self.calendar = calendar or WeekdayTradingCalendar()

    def evaluate_symbol(
        self,
        symbol: str,
        observed_dates: Sequence[date],
        *,
        as_of_date: date,
    ) -> SymbolCompletenessProfile:
        expected = self.calendar.previous_trading_days(
            as_of_date, self.policy.lookback_trading_days
        )
        window_start = expected[0]
        window_end = expected[-1]
        expected_set = set(expected)

        in_window = [
            value for value in observed_dates
            if window_start <= value <= window_end
        ]
        counts: dict[date, int] = {}
        for value in in_window:
            counts[value] = counts.get(value, 0) + 1

        observed_trading = sorted(value for value in counts if value in expected_set)
        missing = tuple(sorted(expected_set - set(observed_trading)))
        duplicate_rows = sum(max(count - 1, 0) for count in counts.values())
        weekend_rows = tuple(sorted(value for value in counts if value.weekday() >= 5))
        holiday_rows = tuple(
            sorted(value for value in counts if value in self.calendar.holidays)
        )

        continuity = (
            100.0 * len(observed_trading) / len(expected)
            if expected else 100.0
        )
        non_trading_count = len(set(weekend_rows) | set(holiday_rows))
        status = self._status(continuity, duplicate_rows, non_trading_count)

        warnings: list[str] = []
        rejection_reasons: list[str] = []
        if missing:
            warnings.append(f"{len(missing)} expected trading days are missing.")
        if duplicate_rows:
            warnings.append(f"{duplicate_rows} duplicate price-history rows detected.")
        if weekend_rows:
            warnings.append(f"{len(weekend_rows)} weekend dates detected.")
        if holiday_rows:
            warnings.append(f"{len(holiday_rows)} holiday dates detected.")
        if status is CompletenessStatus.FAILED:
            rejection_reasons.append(
                "Market-data continuity or anomaly counts violate completeness policy."
            )

        return SymbolCompletenessProfile(
            symbol=symbol.strip().upper(),
            window_start=window_start,
            window_end=window_end,
            expected_trading_days=len(expected),
            observed_trading_days=len(observed_trading),
            missing_trading_days=missing,
            duplicate_row_count=duplicate_rows,
            weekend_row_dates=weekend_rows,
            holiday_row_dates=holiday_rows,
            continuity_percentage=round(continuity, 6),
            status=status,
            warnings=tuple(warnings),
            rejection_reasons=tuple(rejection_reasons),
            metadata={
                "lookback_trading_days": self.policy.lookback_trading_days,
                "non_trading_row_date_count": non_trading_count,
            },
        )

    def evaluate_universe(
        self,
        profiles: Sequence[SymbolCompletenessProfile],
        *,
        canonical_symbol_count: int,
        as_of_date: date,
    ) -> UniverseCompletenessProfile:
        status_counts = {status: 0 for status in CompletenessStatus}
        for profile in profiles:
            status_counts[profile.status] += 1

        continuity_values = [profile.continuity_percentage for profile in profiles]
        average_continuity = (
            sum(continuity_values) / len(continuity_values)
            if continuity_values else 0.0
        )
        minimum_continuity = min(continuity_values, default=0.0)

        worst_status = CompletenessStatus.READY
        rank = {
            CompletenessStatus.READY: 0,
            CompletenessStatus.DEGRADED: 1,
            CompletenessStatus.REVIEW: 2,
            CompletenessStatus.FAILED: 3,
        }
        for profile in profiles:
            if rank[profile.status] > rank[worst_status]:
                worst_status = profile.status
        if not profiles or len(profiles) < canonical_symbol_count:
            worst_status = CompletenessStatus.FAILED

        warnings: list[str] = []
        rejections: list[str] = []
        if any(profile.missing_trading_days for profile in profiles):
            warnings.append("One or more symbols contain missing trading days.")
        if any(profile.duplicate_row_count for profile in profiles):
            warnings.append("One or more symbols contain duplicate rows.")
        if worst_status is CompletenessStatus.FAILED:
            rejections.append("Universe completeness is not production ready.")

        return UniverseCompletenessProfile(
            as_of_date=as_of_date,
            canonical_symbol_count=canonical_symbol_count,
            evaluated_symbol_count=len(profiles),
            ready_symbol_count=status_counts[CompletenessStatus.READY],
            degraded_symbol_count=status_counts[CompletenessStatus.DEGRADED],
            review_symbol_count=status_counts[CompletenessStatus.REVIEW],
            failed_symbol_count=status_counts[CompletenessStatus.FAILED],
            symbols_with_missing_days=sum(
                bool(profile.missing_trading_days) for profile in profiles
            ),
            total_missing_trading_days=sum(
                len(profile.missing_trading_days) for profile in profiles
            ),
            symbols_with_duplicates=sum(
                profile.duplicate_row_count > 0 for profile in profiles
            ),
            total_duplicate_rows=sum(
                profile.duplicate_row_count for profile in profiles
            ),
            symbols_with_non_trading_rows=sum(
                bool(profile.weekend_row_dates or profile.holiday_row_dates)
                for profile in profiles
            ),
            average_continuity_percentage=round(average_continuity, 6),
            minimum_continuity_percentage=round(minimum_continuity, 6),
            status=worst_status,
            symbol_profiles=tuple(profiles),
            warnings=tuple(warnings),
            rejection_reasons=tuple(rejections),
            metadata={"policy": self.policy.__dict__.copy()},
        )

    def _status(
        self,
        continuity: float,
        duplicate_rows: int,
        non_trading_rows: int,
    ) -> CompletenessStatus:
        if (
            continuity >= self.policy.ready_continuity_percentage
            and duplicate_rows <= self.policy.maximum_ready_duplicate_rows
            and non_trading_rows <= self.policy.maximum_ready_non_trading_rows
        ):
            return CompletenessStatus.READY
        if (
            continuity >= self.policy.degraded_continuity_percentage
            and duplicate_rows <= self.policy.maximum_degraded_duplicate_rows
            and non_trading_rows <= self.policy.maximum_degraded_non_trading_rows
        ):
            return CompletenessStatus.DEGRADED
        if continuity >= self.policy.review_continuity_percentage:
            return CompletenessStatus.REVIEW
        return CompletenessStatus.FAILED


class MarketDataCompletenessRepository:
    """Read-only price-history date access supporting SQLAlchemy Session or Engine."""

    def __init__(self, database: Session | Engine) -> None:
        self.database = database

    def fetch_symbol_dates(
        self,
        symbols: Sequence[str],
        *,
        start_date: date,
        end_date: date,
    ) -> dict[str, list[date]]:
        normalized = tuple(sorted({symbol.strip().upper() for symbol in symbols if symbol}))
        result = {symbol: [] for symbol in normalized}
        if not normalized:
            return result

        statement = text(
            """
            SELECT symbol, date
            FROM price_history
            WHERE UPPER(symbol) IN :symbols
              AND date >= :start_date
              AND date <= :end_date
            ORDER BY symbol, date
            """
        ).bindparams(bindparam("symbols", expanding=True))

        if isinstance(self.database, Engine):
            with self.database.connect() as connection:
                rows = connection.execute(
                    statement,
                    {"symbols": normalized, "start_date": start_date, "end_date": end_date},
                )
                for symbol, value in rows:
                    
                    normalized_value = (
                        date.fromisoformat(value)
                        if isinstance(value, str)
                        else value.date()
                        if hasattr(value, "date") and not isinstance(value, date)
                        else value
                    )
                    result.setdefault(str(symbol).strip().upper(), []).append(normalized_value)

        else:
            rows = self.database.execute(
                statement,
                {"symbols": normalized, "start_date": start_date, "end_date": end_date},
            )
            for symbol, value in rows:
                
                    normalized_value = (
                        date.fromisoformat(value)
                        if isinstance(value, str)
                        else value.date()
                        if hasattr(value, "date") and not isinstance(value, date)
                        else value
                    )
                    result.setdefault(str(symbol).strip().upper(), []).append(normalized_value)

        return result


class MarketDataCompletenessService:
    def __init__(
        self,
        database: Session | Engine,
        *,
        policy: MarketDataCompletenessPolicy | None = None,
        calendar: WeekdayTradingCalendar | None = None,
    ) -> None:
        self.engine = MarketDataCompletenessEngine(policy, calendar)
        self.repository = MarketDataCompletenessRepository(database)

    def evaluate(
        self,
        symbols: Sequence[str],
        *,
        as_of_date: date,
    ) -> UniverseCompletenessProfile:
        normalized = tuple(sorted({symbol.strip().upper() for symbol in symbols if symbol}))
        expected = self.engine.calendar.previous_trading_days(
            as_of_date, self.engine.policy.lookback_trading_days
        )
        rows = self.repository.fetch_symbol_dates(
            normalized,
            start_date=expected[0],
            end_date=expected[-1],
        )
        profiles = [
            self.engine.evaluate_symbol(
                symbol,
                rows.get(symbol, ()),
                as_of_date=as_of_date,
            )
            for symbol in normalized
        ]
        return self.engine.evaluate_universe(
            profiles,
            canonical_symbol_count=len(normalized),
            as_of_date=as_of_date,
        )

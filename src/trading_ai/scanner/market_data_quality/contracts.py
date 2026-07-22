from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Iterable


class CoverageStatus(str, Enum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    REVIEW = "REVIEW"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class SymbolCoverageProfile:
    symbol: str
    row_count: int = 0
    trading_day_count: int = 0
    earliest_date: date | None = None
    latest_date: date | None = None
    has_history: bool = False
    meets_minimum_history: bool = False
    status: CoverageStatus = CoverageStatus.REVIEW
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        normalized = self.symbol.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be blank")
        if self.row_count < 0 or self.trading_day_count < 0:
            raise ValueError("coverage counts must be non-negative")
        if self.trading_day_count > self.row_count:
            raise ValueError("trading_day_count cannot exceed row_count")
        if self.earliest_date and self.latest_date and self.earliest_date > self.latest_date:
            raise ValueError("earliest_date cannot be after latest_date")
        object.__setattr__(self, "symbol", normalized)
        object.__setattr__(self, "reasons", tuple(self.reasons))


@dataclass(frozen=True, slots=True)
class UniverseCoverageProfile:
    canonical_symbol_count: int
    symbols_with_history: int
    symbols_without_history: int
    symbols_meeting_minimum_history: int
    symbols_below_minimum_history: int
    coverage_percentage: float
    minimum_history_percentage: float
    minimum_history_days: int
    earliest_available_date: date | None
    latest_available_date: date | None
    status: CoverageStatus
    symbol_profiles: tuple[SymbolCoverageProfile, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        counts = (
            self.canonical_symbol_count,
            self.symbols_with_history,
            self.symbols_without_history,
            self.symbols_meeting_minimum_history,
            self.symbols_below_minimum_history,
            self.minimum_history_days,
        )
        if any(value < 0 for value in counts):
            raise ValueError("coverage counts must be non-negative")
        if self.symbols_with_history + self.symbols_without_history != self.canonical_symbol_count:
            raise ValueError("history counts must equal canonical_symbol_count")
        if self.symbols_meeting_minimum_history + self.symbols_below_minimum_history != self.canonical_symbol_count:
            raise ValueError("minimum-history counts must equal canonical_symbol_count")
        for value in (self.coverage_percentage, self.minimum_history_percentage):
            if value < 0.0 or value > 100.0:
                raise ValueError("coverage percentages must be between 0 and 100")
        if self.earliest_available_date and self.latest_available_date and self.earliest_available_date > self.latest_available_date:
            raise ValueError("earliest_available_date cannot be after latest_available_date")
        object.__setattr__(self, "symbol_profiles", tuple(self.symbol_profiles))
        object.__setattr__(self, "reasons", tuple(self.reasons))

    @property
    def evaluated_symbol_count(self) -> int:
        return len(self.symbol_profiles)

    @property
    def is_ready(self) -> bool:
        return self.status is CoverageStatus.READY

    def symbols_by_status(self, status: CoverageStatus) -> tuple[str, ...]:
        return tuple(profile.symbol for profile in self.symbol_profiles if profile.status is status)

    @classmethod
    def from_profiles(
        cls,
        profiles: Iterable[SymbolCoverageProfile],
        *,
        minimum_history_days: int,
        status: CoverageStatus,
        reasons: Iterable[str] = (),
    ) -> "UniverseCoverageProfile":
        items = tuple(profiles)
        canonical_count = len(items)
        with_history = sum(1 for item in items if item.has_history)
        meets_minimum = sum(1 for item in items if item.meets_minimum_history)
        dates = [item.earliest_date for item in items if item.earliest_date]
        latest_dates = [item.latest_date for item in items if item.latest_date]
        denominator = canonical_count or 1
        return cls(
            canonical_symbol_count=canonical_count,
            symbols_with_history=with_history,
            symbols_without_history=canonical_count - with_history,
            symbols_meeting_minimum_history=meets_minimum,
            symbols_below_minimum_history=canonical_count - meets_minimum,
            coverage_percentage=round(with_history * 100.0 / denominator, 4),
            minimum_history_percentage=round(meets_minimum * 100.0 / denominator, 4),
            minimum_history_days=minimum_history_days,
            earliest_available_date=min(dates) if dates else None,
            latest_available_date=max(latest_dates) if latest_dates else None,
            status=status,
            symbol_profiles=items,
            reasons=tuple(reasons),
        )

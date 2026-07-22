from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .contracts import CoverageStatus, SymbolCoverageProfile, UniverseCoverageProfile


@dataclass(frozen=True, slots=True)
class MarketDataCoveragePolicy:
    minimum_history_days: int = 252
    ready_coverage_percentage: float = 99.0
    degraded_coverage_percentage: float = 95.0
    review_coverage_percentage: float = 80.0
    ready_minimum_history_percentage: float = 95.0
    degraded_minimum_history_percentage: float = 90.0
    fail_on_empty_universe: bool = True

    def __post_init__(self) -> None:
        if self.minimum_history_days < 1:
            raise ValueError("minimum_history_days must be at least 1")
        thresholds = (
            self.ready_coverage_percentage,
            self.degraded_coverage_percentage,
            self.review_coverage_percentage,
            self.ready_minimum_history_percentage,
            self.degraded_minimum_history_percentage,
        )
        if any(value < 0.0 or value > 100.0 for value in thresholds):
            raise ValueError("coverage thresholds must be between 0 and 100")
        if not (
            self.ready_coverage_percentage
            >= self.degraded_coverage_percentage
            >= self.review_coverage_percentage
        ):
            raise ValueError("coverage thresholds must be monotonically decreasing")
        if self.ready_minimum_history_percentage < self.degraded_minimum_history_percentage:
            raise ValueError("minimum-history thresholds must be monotonically decreasing")

    def classify_symbol(self, *, row_count: int, trading_day_count: int) -> tuple[CoverageStatus, tuple[str, ...]]:
        if row_count <= 0 or trading_day_count <= 0:
            return CoverageStatus.FAILED, ("NO_PRICE_HISTORY",)
        if trading_day_count < self.minimum_history_days:
            return CoverageStatus.DEGRADED, (
                f"INSUFFICIENT_HISTORY:{trading_day_count}<{self.minimum_history_days}",
            )
        return CoverageStatus.READY, ()

    def build_symbol_profile(
        self,
        *,
        symbol: str,
        row_count: int,
        trading_day_count: int,
        earliest_date=None,
        latest_date=None,
    ) -> SymbolCoverageProfile:
        status, reasons = self.classify_symbol(
            row_count=row_count,
            trading_day_count=trading_day_count,
        )
        return SymbolCoverageProfile(
            symbol=symbol,
            row_count=row_count,
            trading_day_count=trading_day_count,
            earliest_date=earliest_date,
            latest_date=latest_date,
            has_history=trading_day_count > 0,
            meets_minimum_history=trading_day_count >= self.minimum_history_days,
            status=status,
            reasons=reasons,
        )

    def evaluate(self, profiles: Iterable[SymbolCoverageProfile]) -> UniverseCoverageProfile:
        items = tuple(profiles)
        if not items:
            status = CoverageStatus.FAILED if self.fail_on_empty_universe else CoverageStatus.REVIEW
            return UniverseCoverageProfile.from_profiles(
                items,
                minimum_history_days=self.minimum_history_days,
                status=status,
                reasons=("EMPTY_CANONICAL_UNIVERSE",),
            )

        with_history = sum(1 for item in items if item.has_history)
        meets_minimum = sum(1 for item in items if item.meets_minimum_history)
        total = len(items)
        coverage = with_history * 100.0 / total
        minimum_history_coverage = meets_minimum * 100.0 / total
        reasons: list[str] = []

        if coverage < self.review_coverage_percentage:
            status = CoverageStatus.FAILED
            reasons.append("COVERAGE_BELOW_REVIEW_THRESHOLD")
        elif coverage < self.degraded_coverage_percentage:
            status = CoverageStatus.REVIEW
            reasons.append("COVERAGE_REQUIRES_REVIEW")
        elif coverage < self.ready_coverage_percentage:
            status = CoverageStatus.DEGRADED
            reasons.append("COVERAGE_BELOW_READY_THRESHOLD")
        elif minimum_history_coverage < self.degraded_minimum_history_percentage:
            status = CoverageStatus.REVIEW
            reasons.append("MINIMUM_HISTORY_REQUIRES_REVIEW")
        elif minimum_history_coverage < self.ready_minimum_history_percentage:
            status = CoverageStatus.DEGRADED
            reasons.append("MINIMUM_HISTORY_BELOW_READY_THRESHOLD")
        else:
            status = CoverageStatus.READY

        return UniverseCoverageProfile.from_profiles(
            items,
            minimum_history_days=self.minimum_history_days,
            status=status,
            reasons=reasons,
        )

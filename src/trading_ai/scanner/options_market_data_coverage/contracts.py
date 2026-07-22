from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class GovernanceStatus(str, Enum):
    READY = "READY"
    REVIEW = "REVIEW"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ExpirationCoverageProfile:
    expiration_date: date
    days_to_expiration: int
    contract_count: int
    call_count: int
    put_count: int
    distinct_strikes: int
    minimum_strike: float | None
    maximum_strike: float | None
    median_strike_gap: float | None
    maximum_strike_gap: float | None
    strike_gap_completeness_score: float
    call_put_balance_score: float
    completeness_score: float


@dataclass(frozen=True)
class OptionChainCoverageProfile:
    symbol: str
    quote_date: date
    contract_count: int
    call_count: int
    put_count: int
    expiration_count: int
    distinct_strike_count: int
    minimum_expiration: date | None
    maximum_expiration: date | None
    minimum_dte: int | None
    maximum_dte: int | None
    call_put_ratio: float | None
    call_put_balance_score: float
    expiration_coverage_score: float
    strike_surface_score: float
    overall_coverage_score: float
    governance_status: GovernanceStatus
    governance_reasons: tuple[str, ...] = ()
    expirations: tuple[ExpirationCoverageProfile, ...] = ()


@dataclass(frozen=True)
class OptionChainCoverageRunProfile:
    as_of_date: date
    generated_at: datetime
    source_table: str
    symbols_evaluated: int
    ready_symbols: int
    review_symbols: int
    failed_symbols: int
    average_coverage_score: float
    minimum_coverage_score: float
    maximum_coverage_score: float
    profiles: tuple[OptionChainCoverageProfile, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

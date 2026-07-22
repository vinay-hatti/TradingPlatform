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
class OptionDataReadinessProfile:
    symbol: str
    as_of_date: date

    coverage_status: GovernanceStatus
    quality_status: GovernanceStatus
    readiness_status: GovernanceStatus

    coverage_score: float
    quality_score: float
    readiness_score: float

    contract_count: int
    expiration_count: int
    distinct_strike_count: int

    quote_data_observed: bool
    provider_capability_limited: bool

    coverage_reasons: tuple[str, ...] = ()
    quality_reasons: tuple[str, ...] = ()
    readiness_reasons: tuple[str, ...] = ()
    informational_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class OptionDataReadinessRunProfile:
    as_of_date: date
    generated_at: datetime
    symbols_evaluated: int

    ready_symbols: int
    review_symbols: int
    failed_symbols: int

    average_readiness_score: float
    minimum_readiness_score: float
    maximum_readiness_score: float

    coverage_report_path: str
    quality_report_path: str

    profiles: tuple[OptionDataReadinessProfile, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class GovernanceStatus(str, Enum):
    READY = "READY"
    REVIEW = "REVIEW"
    FAILED = "FAILED"


class ObservationStatus(str, Enum):
    OBSERVED = "OBSERVED"
    PARTIAL = "PARTIAL"
    NOT_OBSERVED = "NOT_OBSERVED"


@dataclass(frozen=True)
class OptionChainQualityProfile:
    symbol: str
    quote_date: date
    contract_count: int

    quoted_contracts: int
    traded_contracts: int
    liquid_contracts: int
    valid_spread_contracts: int
    crossed_market_contracts: int
    locked_market_contracts: int
    negative_market_value_contracts: int

    iv_available_contracts: int
    delta_available_contracts: int
    full_greeks_contracts: int

    quote_observation_status: ObservationStatus
    spread_observation_status: ObservationStatus

    quote_completeness_score: float
    trade_completeness_score: float
    liquidity_score: float
    spread_integrity_score: float
    iv_completeness_score: float
    greeks_completeness_score: float
    overall_quality_score: float

    average_spread_pct: float | None
    median_spread_pct: float | None
    maximum_spread_pct: float | None

    governance_status: GovernanceStatus
    governance_reasons: tuple[str, ...] = ()
    informational_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class OptionChainQualityRunProfile:
    as_of_date: date
    generated_at: datetime
    source_table: str
    symbols_evaluated: int
    ready_symbols: int
    review_symbols: int
    failed_symbols: int
    average_quality_score: float
    minimum_quality_score: float
    maximum_quality_score: float
    quote_data_observed: bool
    quoted_contracts: int
    total_contracts: int
    profiles: tuple[OptionChainQualityProfile, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class SurfaceDecisionStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    REVIEW = "REVIEW"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class SurfaceDecisionPolicy:
    allowed_surface_statuses: tuple[str, ...] = ("READY",)
    minimum_expiration_count: int = 1
    minimum_total_open_interest: int = 1000
    minimum_total_volume: int = 1
    maximum_absolute_term_structure_slope: float = 0.02
    maximum_put_call_open_interest_ratio: float = 10.0
    maximum_put_call_volume_ratio: float = 10.0
    review_missing_term_structure: bool = True
    block_missing_liquidity: bool = True

    def normalized_allowed_statuses(self) -> set[str]:
        return {
            str(value).strip().upper()
            for value in self.allowed_surface_statuses
            if str(value).strip()
        }


@dataclass(frozen=True)
class SurfaceDecisionFeatureProfile:
    underlying_symbol: str
    quote_date: date

    surface_governance_status: str
    decision_status: SurfaceDecisionStatus
    decision_reasons: tuple[str, ...]

    expiration_count: int
    total_contract_count: int
    total_volume: int
    total_open_interest: int

    nearest_atm_implied_volatility: float | None
    farthest_atm_implied_volatility: float | None
    atm_term_structure_slope: float | None

    aggregate_put_call_volume_ratio: float | None
    aggregate_put_call_open_interest_ratio: float | None

    iv_term_structure_regime: str
    options_flow_bias: str
    liquidity_regime: str

    call_signal_adjustment: float
    put_signal_adjustment: float
    confidence_adjustment: float

    feature_version: str = "m35.phase4.step4.v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SurfaceDecisionRunProfile:
    as_of_date: date
    generated_at: datetime
    input_path: str
    output_path: str

    records_read: int
    records_generated: int
    eligible_count: int
    review_count: int
    blocked_count: int

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class AggregateGovernanceStatus(str, Enum):
    READY = "READY"
    REVIEW = "REVIEW"
    EXCLUDED = "EXCLUDED"


@dataclass(frozen=True)
class ExpirationSurfaceRecord:
    underlying_symbol: str
    quote_date: date
    expiry: date
    days_to_expiration: int

    contract_count: int
    call_contract_count: int
    put_contract_count: int
    strike_count: int

    total_volume: int
    total_open_interest: int
    call_volume: int
    put_volume: int
    call_open_interest: int
    put_open_interest: int

    call_put_volume_ratio: float | None
    call_put_open_interest_ratio: float | None

    weighted_implied_volatility: float | None
    call_weighted_implied_volatility: float | None
    put_weighted_implied_volatility: float | None
    atm_implied_volatility: float | None
    downside_put_implied_volatility: float | None
    upside_call_implied_volatility: float | None

    put_skew_25d_minus_atm: float | None
    call_skew_25d_minus_atm: float | None
    risk_reversal_25d: float | None

    near_money_contract_count: int
    downside_put_contract_count: int
    upside_call_contract_count: int

    top_5_open_interest_concentration: float | None
    top_5_volume_concentration: float | None

    governance_status: AggregateGovernanceStatus
    governance_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class SymbolSurfaceProfile:
    underlying_symbol: str
    quote_date: date
    expiration_count: int
    ready_expiration_count: int
    review_expiration_count: int
    excluded_expiration_count: int

    nearest_expiry: date | None
    farthest_expiry: date | None
    nearest_atm_implied_volatility: float | None
    farthest_atm_implied_volatility: float | None
    atm_term_structure_slope: float | None

    total_contract_count: int
    total_volume: int
    total_open_interest: int
    aggregate_put_call_volume_ratio: float | None
    aggregate_put_call_open_interest_ratio: float | None

    governance_status: AggregateGovernanceStatus
    governance_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class OptionSurfaceRunProfile:
    as_of_date: date
    generated_at: datetime
    input_path: str
    expiration_output_path: str
    symbol_output_path: str

    contracts_read: int
    contracts_eligible: int
    contracts_excluded: int
    symbols_evaluated: int
    expirations_evaluated: int

    expiration_ready: int
    expiration_review: int
    expiration_excluded: int

    symbol_ready: int
    symbol_review: int
    symbol_excluded: int

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

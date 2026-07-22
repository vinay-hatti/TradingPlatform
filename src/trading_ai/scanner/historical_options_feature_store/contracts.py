from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class FeatureGovernanceStatus(str, Enum):
    READY = "READY"
    REVIEW = "REVIEW"
    EXCLUDED = "EXCLUDED"


@dataclass(frozen=True)
class HistoricalOptionFeatureRecord:
    underlying_symbol: str
    quote_date: date
    expiry: date
    option_type: str
    strike: float

    days_to_expiration: int
    moneyness: float | None
    log_moneyness: float | None
    intrinsic_value: float | None
    extrinsic_value: float | None

    last_price: float | None
    volume: int | None
    open_interest: int | None
    implied_volatility: float | None
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None

    volume_to_open_interest: float | None
    absolute_delta: float | None
    theta_per_day: float | None
    vega_per_iv_point: float | None

    readiness_status: str
    governance_status: FeatureGovernanceStatus
    governance_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class HistoricalOptionFeatureRunProfile:
    as_of_date: date
    generated_at: datetime
    symbols_considered: int
    symbols_included: int
    symbols_excluded: int
    contracts_read: int
    features_generated: int
    records_ready: int
    records_review: int
    records_excluded: int
    output_path: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

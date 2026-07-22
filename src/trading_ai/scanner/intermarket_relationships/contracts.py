from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class IntermarketGovernanceStatus(str, Enum):
    READY = "READY"
    REVIEW = "REVIEW"
    EXCLUDED = "EXCLUDED"


@dataclass(frozen=True)
class IntermarketRelationshipProfile:
    as_of_date: date

    equity_return_21d: float | None
    growth_relative_strength_21d: float | None
    small_cap_relative_strength_21d: float | None

    volatility_return_21d: float | None
    equity_volatility_spread: float | None

    treasury_return_21d: float | None
    long_duration_relative_strength_21d: float | None
    equity_treasury_spread: float | None

    investment_grade_return_21d: float | None
    high_yield_return_21d: float | None
    credit_risk_spread: float | None

    dollar_return_21d: float | None
    gold_return_21d: float | None
    oil_return_21d: float | None

    equity_dollar_spread: float | None
    equity_gold_spread: float | None
    equity_oil_spread: float | None

    risk_on_score: float
    risk_off_score: float
    market_state: str
    confidence: float

    governance_status: IntermarketGovernanceStatus
    governance_reasons: tuple[str, ...]

    feature_version: str = "m35.phase5.step2.v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IntermarketRunProfile:
    as_of_date: date
    generated_at: datetime
    input_path: str
    output_path: str
    records_read: int
    symbols_available: int
    symbols_missing: int
    market_state: str
    confidence: float
    governance_status: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

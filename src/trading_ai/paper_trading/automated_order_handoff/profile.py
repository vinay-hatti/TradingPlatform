from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AutomatedPaperOrderCandidate:
    candidate_id: str
    portfolio_id: str
    symbol: str
    asset_class: str
    side: str
    quantity: float
    order_type: str = "LIMIT"
    time_in_force: str = "DAY"
    limit_price: float | None = None
    stop_price: float | None = None
    primary_exchange: str = ""
    currency: str = "USD"
    expiry: str = ""
    strike: float | None = None
    right: str = ""
    multiplier: str = ""
    local_symbol: str = ""
    contract_id: int = 0
    institutional_allowed: bool = False
    risk_gateway_allowed: bool = False
    decision_score: float = 0.0
    probability: float = 0.0
    strategy_name: str = "AUTOMATED_PAPER_HANDOFF"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AutomatedPaperOrderCandidate":
        known = {field_name for field_name in cls.__dataclass_fields__}
        unknown = sorted(set(payload) - known)
        if unknown:
            raise ValueError(f"unsupported candidate fields: {', '.join(unknown)}")
        return cls(**payload)


@dataclass(frozen=True)
class AutomatedPaperOrderHandoffAssessment:
    allowed: bool
    score: float
    grade: str
    severity: str
    recommendation: str
    estimated_notional: float
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AutomatedPaperOrderHandoffResult:
    milestone: int
    phase: str
    step: int
    mode: str
    portfolio_id: str
    candidate_id: str
    aggregate_id: str
    client_order_id: str
    idempotency_key: str
    canonical_order_created: bool
    replayed: bool
    assessment: AutomatedPaperOrderHandoffAssessment
    canonical_order: dict[str, Any] | None = None
    ibkr_request: dict[str, Any] | None = None
    broker_submission: dict[str, Any] | None = None
    status: str = "UNKNOWN"
    created_at: str = field(default_factory=utc_now_iso)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

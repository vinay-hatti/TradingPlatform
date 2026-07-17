from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from .instrument_profile import InstrumentMappingProfile

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class BrokerOrderLeg:
    leg_id: str
    instrument: InstrumentMappingProfile
    side: str
    quantity: float
    position_effect: str = "AUTO"
    ratio: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class BrokerOrderRequest:
    client_order_id: str
    account_id: str
    order_type: str
    time_in_force: str
    legs: tuple[BrokerOrderLeg, ...]
    limit_price: float | None = None
    stop_price: float | None = None
    outside_regular_hours: bool = False
    all_or_none: bool = False
    idempotency_key: str | None = None
    strategy_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class BrokerOrderValidationCheck:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class BrokerOrderValidationProfile:
    valid: bool
    allowed: bool
    client_order_id: str
    score: float
    grade: str
    severity: str
    recommendation: str
    order: BrokerOrderRequest | None = None
    checks: tuple[BrokerOrderValidationCheck, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class BrokerOrderSubmissionResult:
    valid: bool
    accepted: bool
    client_order_id: str
    broker_order_id: str | None
    status: str
    submitted_at: str | None = None
    validation: BrokerOrderValidationProfile | None = None
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

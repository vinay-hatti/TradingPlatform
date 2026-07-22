from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class ExecutionOrder:
    execution_order_id: str
    client_order_id: str
    portfolio_id: str
    symbol: str
    strategy: str
    direction: str
    contracts: int
    capital_limit: float
    source_candidate_id: str = ""
    status: str = "PENDING_PRETRADE_RISK"
    risk_status: str = "UNKNOWN"
    approval_status: str = "PENDING"
    broker_order_id: str | None = None
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]: return asdict(self)

@dataclass(frozen=True)
class ExecutionEvent:
    event_id: str
    execution_order_id: str
    event_type: str
    from_status: str
    to_status: str
    occurred_at: str = field(default_factory=utc_now_iso)
    details: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]: return asdict(self)

@dataclass(frozen=True)
class ExecutionWorkflowResult:
    run_id: str
    status: str
    trading_control: str
    intake_count: int
    released_count: int
    blocked_count: int
    review_count: int
    queue_file: str
    event_file: str
    execution_control_file: str
    generated_at: str = field(default_factory=utc_now_iso)
    warnings: tuple[str, ...] = ()
    def to_dict(self) -> dict[str, Any]:
        payload=asdict(self); payload['warnings']=list(self.warnings); return payload

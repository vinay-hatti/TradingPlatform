from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class PositionMark:
    position_id: str
    symbol: str
    price: float
    marked_at: str = field(default_factory=utc_now_iso)
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]: return asdict(self)

@dataclass(frozen=True)
class PositionAssessment:
    assessment_id: str
    position_id: str
    portfolio_id: str
    symbol: str
    strategy_type: str
    direction: str
    quantity: int
    entry_price: float
    current_price: float
    unrealized_pnl: float
    return_pct: float
    holding_days: int
    data_age_minutes: float
    decision: str
    urgency: str
    reasons: tuple[str, ...] = ()
    recommended_quantity: int = 0
    generated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self); payload["reasons"] = list(self.reasons); return payload

@dataclass(frozen=True)
class ExitInstruction:
    instruction_id: str
    assessment_id: str
    position_id: str
    portfolio_id: str
    symbol: str
    action: str
    quantity: int
    order_type: str
    limit_price: float | None
    status: str
    urgency: str
    reasons: tuple[str, ...]
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self); payload["reasons"] = list(self.reasons); return payload

@dataclass(frozen=True)
class MonitoringWorkflowResult:
    run_id: str
    status: str
    assessed_count: int
    hold_count: int
    reduce_count: int
    close_count: int
    review_count: int
    stale_count: int
    assessment_file: str
    instruction_file: str
    report_file: str
    generated_at: str = field(default_factory=utc_now_iso)
    warnings: tuple[str, ...] = ()
    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self); payload["warnings"] = list(self.warnings); return payload

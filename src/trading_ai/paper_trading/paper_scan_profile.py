from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class PaperScanCandidate:
    candidate_id: str
    symbol: str
    strategy_name: str
    asset_class: str
    direction: str
    score: float
    probability: float
    market_price: float | None
    quantity: float
    order_type: str = "LIMIT"
    time_in_force: str = "DAY"
    limit_price: float | None = None
    stop_price: float | None = None
    expiration: str | None = None
    strike: float | None = None
    option_type: str | None = None
    sector: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PaperDecisionPipelineResult:
    candidate_id: str
    symbol: str
    strategy_name: str
    approved: bool
    score: float
    probability: float
    recommendation: str
    institutional_decision: Any = None
    risk_gateway_decision: Any = None
    rejection_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PaperOrderDraft:
    candidate_id: str
    aggregate_id: str
    client_order_id: str
    account_id: str
    idempotency_key: str
    strategy_name: str
    command: Any
    risk_metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PaperScanCycleResult:
    session_id: str
    cycle_id: str
    scanned_symbols: tuple[str, ...]
    candidate_count: int
    approved_count: int
    rejected_count: int
    order_draft_count: int
    candidates: tuple[PaperScanCandidate, ...] = ()
    decisions: tuple[PaperDecisionPipelineResult, ...] = ()
    order_drafts: tuple[PaperOrderDraft, ...] = ()
    errors: tuple[str, ...] = ()
    started_at: str = field(default_factory=utc_now_iso)
    completed_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

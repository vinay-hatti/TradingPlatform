from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class MarketDataSnapshot:
    symbol: str
    timestamp: str
    price: float
    volume: float = 0.0
    source: str = "unknown"
    asset_class: str = "EQUITY"
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ReconciliationCheckProfile:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class MarketDataReconciliationProfile:
    valid: bool
    allowed: bool
    symbol: str
    score: float
    grade: str
    severity: str
    recommendation: str
    price_difference: float | None
    price_difference_pct: float | None
    volume_difference: float | None
    volume_difference_pct: float | None
    timestamp_difference_seconds: float | None
    checks: tuple[ReconciliationCheckProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    live_snapshot: MarketDataSnapshot | None = None
    historical_snapshot: MarketDataSnapshot | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class MarketDataReconciliationSummary:
    valid: bool
    allowed: bool
    total_count: int
    matched_count: int
    warning_count: int
    rejected_count: int
    score: float
    grade: str
    severity: str
    recommendation: str
    profiles: tuple[MarketDataReconciliationProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

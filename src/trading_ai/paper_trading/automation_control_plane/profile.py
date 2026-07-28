from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AutomationPhaseStatus:
    phase: int
    name: str
    required: bool
    status: str
    input_path: str = ""
    output_path: str = ""
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AutomationControlDecision:
    allowed: bool
    mode: str
    reason_codes: tuple[str, ...]
    kill_switch_active: bool
    paper_routing_enabled: bool
    live_trading_enabled: bool
    required_confirmation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AutomatedTradingCycleResult:
    milestone: int
    phase: int
    cycle_id: str
    portfolio_id: str
    mode: str
    status: str
    control_decision: dict[str, Any]
    phases: tuple[dict[str, Any], ...]
    consolidated_summary: dict[str, Any]
    audit_events: tuple[dict[str, Any], ...]
    started_at: str
    completed_at: str
    duration_seconds: float
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

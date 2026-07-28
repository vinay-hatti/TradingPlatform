from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ScheduledPhaseCommand:
    phase: int
    name: str
    command: tuple[str, ...]
    required: bool = True
    timeout_seconds: int = 900
    retry_limit: int = 1
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScheduledPhaseExecution:
    phase: int
    name: str
    status: str
    attempt_count: int
    exit_code: int | None
    started_at: str
    completed_at: str
    duration_seconds: float
    stdout_tail: str = ""
    stderr_tail: str = ""
    report_path: str = ""
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AutomationScheduleDecision:
    allowed: bool
    schedule_name: str
    run_key: str
    reason_codes: tuple[str, ...]
    duplicate_run: bool
    market_window_allowed: bool
    kill_switch_active: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AutomationScheduledRunResult:
    milestone: int
    phase: int
    run_id: str
    run_key: str
    schedule_name: str
    portfolio_id: str
    mode: str
    status: str
    decision: dict[str, Any]
    executions: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    started_at: str
    completed_at: str
    duration_seconds: float
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

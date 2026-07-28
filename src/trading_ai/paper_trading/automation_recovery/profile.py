from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RecoveryCheckpoint:
    checkpoint_id: str
    run_key: str
    phase: int
    status: str
    completed: bool
    report_path: str = ""
    checksum: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecoveryAction:
    sequence: int
    action_code: str
    phase: int | None
    action: str
    reason: str
    safe_to_replay: bool
    requires_confirmation: bool
    command: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecoveryAuthorization:
    allowed: bool
    mode: str
    reason_codes: tuple[str, ...]
    required_confirmation: str = ""
    kill_switch_active: bool = False
    live_trading_enabled: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AutomationRecoveryResult:
    milestone: int
    phase: int
    portfolio_id: str
    source_run_key: str
    recovery_id: str
    status: str
    authorization: dict[str, Any]
    checkpoints: tuple[dict[str, Any], ...]
    actions: tuple[dict[str, Any], ...]
    verification: dict[str, Any]
    created_at: str = field(default_factory=utc_now_iso)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

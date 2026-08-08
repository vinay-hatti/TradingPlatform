from __future__ import annotations
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

class AutomationMode(str, Enum):
    ADVISORY = "ADVISORY"
    SEMI_AUTOMATIC = "SEMI_AUTOMATIC"
    FULLY_AUTOMATIC = "FULLY_AUTOMATIC"

@dataclass(frozen=True)
class ManagementEvaluation:
    position_id: str
    symbol: str
    automation_mode: str
    underlying_price: float | None
    option_mark: float | None
    days_to_expiry: int | None
    current_stop: float | None
    next_target: float | None
    triggered_instructions: tuple[dict[str, Any], ...]
    trailing_stop_updated: bool
    thesis_integrity: float
    status: str
    evaluated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class ManagementCycleResult:
    requested: int
    evaluated: int
    triggered: int
    advisory: int
    pending_approval: int
    submitted: int
    failed: int
    errors: tuple[str, ...]
    evaluations: tuple[ManagementEvaluation, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

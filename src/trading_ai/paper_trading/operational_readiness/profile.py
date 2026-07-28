from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ReadinessControl:
    control_id: str
    category: str
    title: str
    status: str
    score: float
    weight: float
    evidence: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    recommendation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReadinessCategoryScore:
    category: str
    score: float
    status: str
    control_count: int
    passed: int
    warned: int
    failed: int


@dataclass(frozen=True)
class OperationalReadinessResult:
    milestone: int
    phase: int
    portfolio_id: str
    mode: str
    overall_status: str
    recommendation: str
    overall_score: float
    category_scores: tuple[dict[str, Any], ...]
    controls: tuple[dict[str, Any], ...]
    acceptance_summary: dict[str, Any]
    sign_off: dict[str, Any]
    created_at: str = field(default_factory=utc_now_iso)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

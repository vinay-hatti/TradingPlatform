from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .profile import utc_now_iso


@dataclass(frozen=True)
class PositionLifecycleEvent:
    event_id: str
    portfolio_id: str
    position_id: str
    symbol: str
    strategy_id: str
    event_type: str
    source_status: str
    registry_status_before: str
    registry_status_after: str
    action: str
    source_artifact: str
    source_fingerprint: str
    occurred_at: str = field(default_factory=utc_now_iso)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PositionReconciliationException:
    exception_id: str
    portfolio_id: str
    position_id: str
    symbol: str
    strategy_id: str
    exception_type: str
    severity: str
    message: str
    source_artifact: str
    detected_at: str = field(default_factory=utc_now_iso)
    resolved: bool = False
    resolution: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PositionLifecycleJournal:
    portfolio_id: str
    events: tuple[PositionLifecycleEvent, ...] = field(default_factory=tuple)
    exceptions: tuple[PositionReconciliationException, ...] = field(default_factory=tuple)
    generated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "event_count": len(self.events),
            "exception_count": len(self.exceptions),
            "unresolved_exception_count": sum(not item.resolved for item in self.exceptions),
            "events": [item.to_dict() for item in self.events],
            "exceptions": [item.to_dict() for item in self.exceptions],
            "generated_at": self.generated_at,
        }


@dataclass(frozen=True)
class PositionReconciliationResult:
    source_artifact: str
    source_type: str
    status: str
    position_id: str = ""
    symbol: str = ""
    strategy_id: str = ""
    action: str = "NONE"
    duplicate: bool = False
    repaired: bool = False
    exception_ids: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["exception_ids"] = list(self.exception_ids)
        payload["warnings"] = list(self.warnings)
        return payload

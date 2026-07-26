from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any

from .governance import PublishedStateFinding


@dataclass(frozen=True)
class PublishedMarketState:
    publication_name: str
    run_id: str
    published_at: datetime
    as_of_date: date
    market_intelligence_timestamp: datetime
    option_snapshot_timestamp: datetime | None
    option_snapshot_id: str | None
    readiness_status: str
    scanner_ready: bool
    decision_context_ready: bool
    details: dict[str, Any]
    age_seconds: float
    degraded: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("published_at", "as_of_date", "market_intelligence_timestamp", "option_snapshot_timestamp"):
            value = payload.get(key)
            if value is not None:
                payload[key] = value.isoformat()
        return payload


@dataclass(frozen=True)
class PublishedStateResolution:
    status: str
    state: PublishedMarketState | None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    findings: tuple[PublishedStateFinding, ...] = ()
    consumer: str = "generic"

    @property
    def usable(self) -> bool:
        return self.state is not None and not self.errors

    @property
    def failure_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.findings if item.blocking)

    @property
    def warning_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.findings if not item.blocking)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "usable": self.usable,
            "consumer": self.consumer,
            "state": self.state.to_dict() if self.state else None,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "failure_codes": list(self.failure_codes),
            "warning_codes": list(self.warning_codes),
            "findings": [item.to_dict() for item in self.findings],
        }

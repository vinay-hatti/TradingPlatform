from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class PortfolioPhaseReadiness:
    portfolio_id: str
    generated_at: str
    status: str
    checks: dict[str, bool]
    warnings: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PortfolioPhaseReport:
    portfolio_id: str
    generated_at: str
    phase: str
    status: str
    registry: dict[str, Any]
    exposure: dict[str, Any]
    lifecycle: dict[str, Any]
    audit: dict[str, Any]
    database: dict[str, Any]
    readiness: PortfolioPhaseReadiness
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["readiness"] = self.readiness.to_dict()
        return payload

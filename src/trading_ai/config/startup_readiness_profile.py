from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class StartupGateCheckProfile:
    name: str
    category: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StartupReadinessProfile:
    valid: bool
    allowed: bool
    environment: str
    score: float
    grade: str
    severity: str
    recommendation: str
    active_environment_version: str | None = None
    configuration_fingerprint: str | None = None
    registered_configuration_fingerprint: str | None = None
    runtime_score: float | None = None
    environment_score: float | None = None
    secret_score: float | None = None
    checks: tuple[StartupGateCheckProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    runtime_profile: dict[str, Any] | None = None
    environment_profile: dict[str, Any] | None = None
    secret_profile: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

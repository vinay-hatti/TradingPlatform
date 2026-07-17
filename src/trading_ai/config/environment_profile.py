from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class EnvironmentProfile:
    name: str
    version: str
    status: str
    configuration: dict[str, Any]
    configuration_hash: str
    runtime_score: float = 0.0
    runtime_grade: str = "N/A"
    runtime_allowed: bool = False
    created_by: str = "system"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_environment: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EnvironmentPromotionProfile:
    valid: bool
    allowed: bool
    source_environment: str
    target_environment: str
    source_version: str
    target_version: str | None
    promotion_score: float
    grade: str
    severity: str
    recommendation: str
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EnvironmentRegistryProfile:
    environments: dict[str, tuple[EnvironmentProfile, ...]]
    active_versions: dict[str, str]
    promotion_history: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

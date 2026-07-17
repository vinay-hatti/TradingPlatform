from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SecretInventoryEntryProfile:
    name: str
    environment: str
    provider: str
    owner: str | None
    created_at: str
    rotated_at: str | None = None
    expires_at: str | None = None
    version: str = "1"
    fingerprint: str | None = None
    enabled: bool = True
    required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CredentialHealthCheckProfile:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CredentialHealthProfile:
    name: str
    environment: str
    valid: bool
    allowed: bool
    resolved: bool
    provider: str
    age_days: float | None
    days_until_expiry: float | None
    score: float
    grade: str
    severity: str
    rotation_required: bool
    recommendation: str
    checks: tuple[CredentialHealthCheckProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class SecretGovernanceProfile:
    valid: bool
    allowed: bool
    environment: str
    secret_count: int
    healthy_count: int
    warning_count: int
    rejected_count: int
    score: float
    grade: str
    severity: str
    recommendation: str
    credentials: tuple[CredentialHealthProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SecretRotationProfile:
    valid: bool
    allowed: bool
    name: str
    environment: str
    previous_version: str | None
    new_version: str
    previous_fingerprint: str | None
    new_fingerprint: str
    actor: str
    reason: str
    promotion_score: float
    grade: str
    severity: str
    recommendation: str
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

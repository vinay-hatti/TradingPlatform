from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ValidationFinding:
    check_id: str
    category: str
    severity: str
    status: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    remediation: str = ''
    observed_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class ValidationCheckResult:
    check_id: str
    category: str
    passed: bool
    score: float
    findings: tuple[ValidationFinding, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass(frozen=True)
class ReleaseReadinessResult:
    release_id: str
    version: str
    environment: str
    score: float
    threshold: float
    ready: bool
    critical_findings: int
    warning_findings: int
    checks: tuple[ValidationCheckResult, ...]
    recommendation: str
    evaluated_at: str = field(default_factory=utc_now_iso)

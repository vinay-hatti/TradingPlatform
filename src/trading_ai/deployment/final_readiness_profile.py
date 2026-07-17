from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ValidationCheck:
    check_id: str
    category: str
    required: bool
    passed: bool
    score: float
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""


@dataclass(frozen=True)
class BenchmarkResult:
    benchmark_id: str
    category: str
    metric_name: str
    observed_value: float
    threshold_value: float
    comparison: str
    passed: bool
    duration_seconds: float
    notes: str = ""


@dataclass(frozen=True)
class RegressionResult:
    suite_name: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    pass_rate: float
    passed: bool
    duration_seconds: float
    output: str = ""


@dataclass(frozen=True)
class ReleaseSignOff:
    release_id: str
    release_version: str
    approved_by: tuple[str, ...]
    approval_roles: tuple[str, ...]
    final_decision: str
    comments: str
    signed_at: str = field(default_factory=utc_now_iso)


@dataclass(frozen=True)
class FinalReadinessResult:
    project_name: str
    milestone: str
    phase: str
    overall_score: float
    ready_for_production: bool
    critical_findings: int
    high_findings: int
    regression_pass_rate: float
    benchmark_pass_rate: float
    documentation_score: float
    checks: tuple[ValidationCheck, ...]
    benchmarks: tuple[BenchmarkResult, ...]
    regressions: tuple[RegressionResult, ...]
    sign_off: ReleaseSignOff | None
    recommendation: str
    evaluated_at: str = field(default_factory=utc_now_iso)

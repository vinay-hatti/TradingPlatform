from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class StepExecutionStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class PhaseClosurePolicy:
    fail_on_missing_artifact: bool = True
    fail_on_nonzero_command: bool = True
    require_step1_run_report: bool = True
    require_step2_run_report: bool = True
    require_step3_run_report: bool = True
    require_step4_run_report: bool = True


@dataclass(frozen=True)
class StepExecutionResult:
    step_name: str
    command: tuple[str, ...]
    status: StepExecutionStatus
    return_code: int | None
    stdout: str
    stderr: str
    started_at: datetime
    completed_at: datetime


@dataclass(frozen=True)
class PhaseClosureRunProfile:
    as_of_date: date
    generated_at: datetime
    execution_results: tuple[StepExecutionResult, ...]

    required_artifacts: tuple[str, ...]
    existing_artifacts: tuple[str, ...]
    missing_artifacts: tuple[str, ...]

    phase_status: str
    phase_reasons: tuple[str, ...]

    consolidated_metrics: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

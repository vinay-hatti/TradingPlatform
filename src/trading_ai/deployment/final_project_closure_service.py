from __future__ import annotations

from pathlib import Path

from .final_readiness_engine import FinalReadinessEngine
from .final_readiness_profile import (
    BenchmarkResult,
    FinalReadinessResult,
    RegressionResult,
    ReleaseSignOff,
    ValidationCheck,
)
from .release_documentation_service import ReleaseDocumentationService


class FinalProjectClosureService:
    def __init__(
        self,
        engine: FinalReadinessEngine | None = None,
    ) -> None:
        self.engine = engine or FinalReadinessEngine()
        self.documentation = ReleaseDocumentationService()

    def evaluate(
        self,
        *,
        root: str | Path,
        project_name: str,
        checks: tuple[ValidationCheck, ...],
        benchmarks: tuple[BenchmarkResult, ...],
        regressions: tuple[RegressionResult, ...],
        sign_off: ReleaseSignOff | None,
    ) -> FinalReadinessResult:
        documentation_score, documentation_checks = (
            self.documentation.evaluate(
                root=root,
                additional_required=(
                    "updated_PROJECT_STATUS.md",
                    "INSTALL.md",
                ),
            )
        )
        return self.engine.evaluate(
            project_name=project_name,
            milestone="Milestone 30",
            phase="Phase 10",
            checks=checks + documentation_checks,
            benchmarks=benchmarks,
            regressions=regressions,
            documentation_score=documentation_score,
            sign_off=sign_off,
        )

from __future__ import annotations

import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Sequence

from .contracts import (
    PhaseClosurePolicy,
    PhaseClosureRunProfile,
    StepExecutionResult,
    StepExecutionStatus,
)
from .serialization import load_json


class OptionSurfacePhaseClosureService:
    def __init__(
        self,
        policy: PhaseClosurePolicy | None = None,
    ) -> None:
        self.policy = policy or PhaseClosurePolicy()

    def run(
        self,
        *,
        as_of_date: date,
        project_root: str | Path,
        execute_pipeline: bool,
        include_review: bool,
    ) -> PhaseClosureRunProfile:
        root = Path(project_root).resolve()
        commands = self._commands(
            as_of_date=as_of_date,
            include_review=include_review,
        )

        execution_results: list[StepExecutionResult] = []
        if execute_pipeline:
            for step_name, command in commands:
                execution_results.append(
                    self._execute(
                        root=root,
                        step_name=step_name,
                        command=command,
                    )
                )
                if (
                    execution_results[-1].status
                    == StepExecutionStatus.FAILED
                    and self.policy.fail_on_nonzero_command
                ):
                    break
        else:
            now = datetime.now(timezone.utc)
            execution_results = [
                StepExecutionResult(
                    step_name=step_name,
                    command=tuple(command),
                    status=StepExecutionStatus.SKIPPED,
                    return_code=None,
                    stdout="",
                    stderr="",
                    started_at=now,
                    completed_at=now,
                )
                for step_name, command in commands
            ]

        required = self._required_artifacts(root)
        existing = tuple(
            str(path.relative_to(root))
            for path in required
            if path.exists()
        )
        missing = tuple(
            str(path.relative_to(root))
            for path in required
            if not path.exists()
        )

        reasons: list[str] = []
        failed_steps = [
            result.step_name
            for result in execution_results
            if result.status == StepExecutionStatus.FAILED
        ]
        if failed_steps:
            reasons.append(
                "failed pipeline steps: " + ", ".join(failed_steps)
            )
        if missing:
            reasons.append(
                "missing required artifacts: " + ", ".join(missing)
            )

        phase_status = "COMPLETE"
        if failed_steps:
            phase_status = "FAILED"
        elif missing:
            phase_status = (
                "FAILED"
                if self.policy.fail_on_missing_artifact
                else "REVIEW"
            )

        metrics = self._consolidated_metrics(root)

        return PhaseClosureRunProfile(
            as_of_date=as_of_date,
            generated_at=datetime.now(timezone.utc),
            execution_results=tuple(execution_results),
            required_artifacts=tuple(
                str(path.relative_to(root)) for path in required
            ),
            existing_artifacts=existing,
            missing_artifacts=missing,
            phase_status=phase_status,
            phase_reasons=tuple(reasons),
            consolidated_metrics=metrics,
            metadata={
                "include_review": include_review,
                "execute_pipeline": execute_pipeline,
                "phase": "Milestone 35 Phase 4",
            },
        )

    def _commands(
        self,
        *,
        as_of_date: date,
        include_review: bool,
    ) -> list[tuple[str, list[str]]]:
        iso_date = as_of_date.isoformat()

        step1 = [
            "uv",
            "run",
            "python",
            "scripts/run_m35_phase4_historical_options_feature_store.py",
            "--as-of-date",
            iso_date,
            "--readiness-report",
            "reports/m35/phase3/readiness/run.json",
        ]
        if include_review:
            step1.append("--include-review")

        step2 = [
            "uv",
            "run",
            "python",
            "scripts/run_m35_phase4_option_surface_analytics.py",
            "--as-of-date",
            iso_date,
            "--feature-input",
            (
                "reports/m35/phase4/"
                "historical_options_feature_store/features.jsonl"
            ),
        ]
        if include_review:
            step2.append("--include-review-features")

        step3 = [
            "uv",
            "run",
            "python",
            "scripts/run_m35_phase4_surface_persistence.py",
            "--as-of-date",
            iso_date,
        ]
        if not include_review:
            step3.append("--ready-only")

        step4 = [
            "uv",
            "run",
            "python",
            (
                "scripts/"
                "run_m35_phase4_surface_decision_integration.py"
            ),
            "--as-of-date",
            iso_date,
        ]
        if include_review:
            step4.append("--include-review-surfaces")

        return [
            ("Phase 4 Step 1", step1),
            ("Phase 4 Step 2", step2),
            ("Phase 4 Step 3", step3),
            ("Phase 4 Step 4", step4),
        ]

    def _execute(
        self,
        *,
        root: Path,
        step_name: str,
        command: Sequence[str],
    ) -> StepExecutionResult:
        started = datetime.now(timezone.utc)
        completed = started
        try:
            result = subprocess.run(
                list(command),
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            completed = datetime.now(timezone.utc)
            status = (
                StepExecutionStatus.PASSED
                if result.returncode == 0
                else StepExecutionStatus.FAILED
            )
            return StepExecutionResult(
                step_name=step_name,
                command=tuple(command),
                status=status,
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                started_at=started,
                completed_at=completed,
            )
        except Exception as exc:
            completed = datetime.now(timezone.utc)
            return StepExecutionResult(
                step_name=step_name,
                command=tuple(command),
                status=StepExecutionStatus.FAILED,
                return_code=None,
                stdout="",
                stderr=str(exc),
                started_at=started,
                completed_at=completed,
            )

    def _required_artifacts(self, root: Path) -> tuple[Path, ...]:
        paths = []

        if self.policy.require_step1_run_report:
            paths.extend(
                [
                    root
                    / "reports/m35/phase4/"
                    "historical_options_feature_store/run.json",
                    root
                    / "reports/m35/phase4/"
                    "historical_options_feature_store/features.jsonl",
                ]
            )

        if self.policy.require_step2_run_report:
            paths.extend(
                [
                    root
                    / "reports/m35/phase4/"
                    "option_surface_analytics/run.json",
                    root
                    / "reports/m35/phase4/"
                    "option_surface_analytics/"
                    "expiration_surfaces.jsonl",
                    root
                    / "reports/m35/phase4/"
                    "option_surface_analytics/"
                    "symbol_surface_profiles.jsonl",
                ]
            )

        if self.policy.require_step3_run_report:
            paths.extend(
                [
                    root
                    / "reports/m35/phase4/"
                    "option_surface_persistence/run.json",
                    root
                    / "reports/m35/phase4/"
                    "option_surface_persistence/"
                    "expiration_surfaces.csv",
                    root
                    / "reports/m35/phase4/"
                    "option_surface_persistence/"
                    "symbol_surface_profiles.csv",
                    root
                    / "reports/m35/phase4/"
                    "option_surface_persistence/"
                    "governance_summary.json",
                ]
            )

        if self.policy.require_step4_run_report:
            paths.extend(
                [
                    root
                    / "reports/m35/phase4/"
                    "option_surface_decision_integration/run.json",
                    root
                    / "reports/m35/phase4/"
                    "option_surface_decision_integration/"
                    "surface_decision_features.jsonl",
                ]
            )

        return tuple(paths)

    @staticmethod
    def _consolidated_metrics(root: Path) -> dict:
        reports = {
            "step1": root
            / "reports/m35/phase4/"
            "historical_options_feature_store/run.json",
            "step2": root
            / "reports/m35/phase4/"
            "option_surface_analytics/run.json",
            "step3": root
            / "reports/m35/phase4/"
            "option_surface_persistence/run.json",
            "step4": root
            / "reports/m35/phase4/"
            "option_surface_decision_integration/run.json",
        }

        metrics = {}
        for step, path in reports.items():
            if path.exists():
                metrics[step] = load_json(path)
        return metrics

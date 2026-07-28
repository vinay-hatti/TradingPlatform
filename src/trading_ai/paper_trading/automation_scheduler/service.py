from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Iterable

from .engine import AutomationSchedulerEngine, stable_run_id
from .policy import AutomationSchedulerPolicy
from .profile import (
    AutomationScheduledRunResult,
    ScheduledPhaseCommand,
    ScheduledPhaseExecution,
)
from .repository import AutomationRunStateRepository
from .runner import SubprocessPhaseRunner


class AutomationSchedulerService:
    def __init__(
        self,
        state_repository: AutomationRunStateRepository,
        *,
        policy: AutomationSchedulerPolicy | None = None,
        runner: SubprocessPhaseRunner | None = None,
    ) -> None:
        self.policy = policy or AutomationSchedulerPolicy()
        self.policy.validate()
        self.engine = AutomationSchedulerEngine(self.policy)
        self.repository = state_repository
        self.runner = runner or SubprocessPhaseRunner()

    def execute(
        self,
        portfolio_id: str,
        schedule_name: str,
        run_key: str,
        commands: Iterable[ScheduledPhaseCommand],
        *,
        mode: str = "DRY_RUN",
        confirmation: str = "",
        require_market_window: bool = False,
        now: datetime | None = None,
    ) -> AutomationScheduledRunResult:
        started = now or datetime.now(timezone.utc)
        decision = self.engine.authorize(
            portfolio_id,
            schedule_name,
            run_key,
            mode=mode,
            existing_run_keys=self.repository.existing_run_keys(),
            confirmation=confirmation,
            require_market_window=require_market_window,
            now=started,
        )
        run_id = stable_run_id(portfolio_id, schedule_name, run_key)

        executions: list[ScheduledPhaseExecution] = []
        warnings: list[str] = []
        errors: list[str] = []

        if decision.allowed:
            for command in sorted(commands, key=lambda item: item.phase):
                result = self.runner.execute(command)
                executions.append(result)
                warnings.extend(result.warnings)
                errors.extend(result.errors)
                if (
                    result.status == "FAILED"
                    and command.required
                    and self.policy.stop_on_required_phase_failure
                ):
                    break
                if (
                    result.status == "FAILED"
                    and not command.required
                    and not self.policy.continue_on_optional_phase_failure
                ):
                    break
            status = self.engine.final_status(executions)
        else:
            errors.extend(decision.reason_codes)
            status = "PHASE6_SCHEDULED_RUN_BLOCKED"

        summary = self.engine.summarize(executions)
        if summary["total_errors"] > self.policy.maximum_total_errors:
            errors.append("MAXIMUM_TOTAL_ERRORS_EXCEEDED")
        if summary["total_warnings"] > self.policy.maximum_total_warnings:
            warnings.append("MAXIMUM_TOTAL_WARNINGS_EXCEEDED")

        completed = datetime.now(timezone.utc)
        result = AutomationScheduledRunResult(
            milestone=51,
            phase=6,
            run_id=run_id,
            run_key=run_key,
            schedule_name=schedule_name,
            portfolio_id=portfolio_id,
            mode=mode.upper(),
            status=status,
            decision=asdict(decision),
            executions=tuple(asdict(row) for row in executions),
            summary=summary,
            started_at=started.isoformat(),
            completed_at=completed.isoformat(),
            duration_seconds=round(
                (completed - started).total_seconds(), 6
            ),
            warnings=tuple(dict.fromkeys(warnings)),
            errors=tuple(dict.fromkeys(errors)),
            metadata={
                "environment": "PAPER",
                "live_trading_enabled": False,
                "restart_safe": True,
                "duplicate_run_prevention": self.policy.prevent_duplicate_runs,
            },
        )
        self.repository.save_run(run_key, result.to_dict())
        return result

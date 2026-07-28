from __future__ import annotations

import hashlib
from datetime import datetime, time, timezone
from typing import Iterable, Mapping

from .policy import AutomationSchedulerPolicy
from .profile import AutomationScheduleDecision, ScheduledPhaseExecution


def stable_run_id(portfolio_id: str, schedule_name: str, run_key: str) -> str:
    digest = hashlib.sha256(
        f"{portfolio_id}|{schedule_name}|{run_key}".encode()
    ).hexdigest()[:24]
    return f"M51-SCHEDULE-{digest.upper()}"


class AutomationSchedulerEngine:
    def __init__(
        self,
        policy: AutomationSchedulerPolicy | None = None,
    ) -> None:
        self.policy = policy or AutomationSchedulerPolicy()
        self.policy.validate()

    @staticmethod
    def within_market_window(
        current: datetime,
        *,
        start_hour: int = 8,
        start_minute: int = 0,
        end_hour: int = 17,
        end_minute: int = 0,
    ) -> bool:
        if current.weekday() >= 5:
            return False
        current_time = current.timetz().replace(tzinfo=None)
        return time(start_hour, start_minute) <= current_time <= time(
            end_hour, end_minute
        )

    def authorize(
        self,
        portfolio_id: str,
        schedule_name: str,
        run_key: str,
        *,
        mode: str,
        existing_run_keys: Iterable[str] = (),
        confirmation: str = "",
        require_market_window: bool = False,
        now: datetime | None = None,
    ) -> AutomationScheduleDecision:
        normalized = mode.upper()
        reasons: list[str] = []
        current = now or datetime.now(timezone.utc)
        duplicate = run_key in set(existing_run_keys)
        market_allowed = (
            self.within_market_window(current)
            if require_market_window
            else True
        )

        if normalized not in self.policy.allowed_modes:
            reasons.append("MODE_NOT_ALLOWED")
        if self.policy.live_trading_enabled:
            reasons.append("LIVE_TRADING_ENABLED")
        if self.policy.kill_switch_active:
            reasons.append("KILL_SWITCH_ACTIVE")
        if self.policy.prevent_duplicate_runs and duplicate:
            reasons.append("DUPLICATE_RUN_KEY")
        if not market_allowed:
            reasons.append("OUTSIDE_MARKET_WINDOW")
        if normalized == "SUBMIT":
            expected = self.policy.submit_confirmation_template.format(
                portfolio_id=portfolio_id,
                run_key=run_key,
            )
            if confirmation != expected:
                reasons.append("CONFIRMATION_MISMATCH")

        return AutomationScheduleDecision(
            allowed=not reasons,
            schedule_name=schedule_name,
            run_key=run_key,
            reason_codes=tuple(dict.fromkeys(reasons)),
            duplicate_run=duplicate,
            market_window_allowed=market_allowed,
            kill_switch_active=self.policy.kill_switch_active,
            metadata={
                "environment": self.policy.environment,
                "mode": normalized,
                "evaluated_at": current.isoformat(),
            },
        )

    def summarize(
        self,
        executions: Iterable[ScheduledPhaseExecution],
    ) -> dict[str, int | float]:
        rows = tuple(executions)
        return {
            "phase_count": len(rows),
            "completed": sum(row.status == "COMPLETED" for row in rows),
            "failed": sum(row.status == "FAILED" for row in rows),
            "skipped": sum(row.status == "SKIPPED" for row in rows),
            "retried": sum(row.attempt_count > 1 for row in rows),
            "total_warnings": sum(len(row.warnings) for row in rows),
            "total_errors": sum(len(row.errors) for row in rows),
            "duration_seconds": round(
                sum(row.duration_seconds for row in rows), 6
            ),
        }

    def final_status(
        self,
        executions: Iterable[ScheduledPhaseExecution],
    ) -> str:
        rows = tuple(executions)
        if any(row.status == "FAILED" and row.metadata.get("required") for row in rows):
            return "PHASE6_SCHEDULED_RUN_FAILED"
        if any(row.status == "FAILED" for row in rows):
            return "PHASE6_SCHEDULED_RUN_COMPLETED_WITH_FAILURES"
        if any(row.warnings for row in rows):
            return "PHASE6_SCHEDULED_RUN_COMPLETED_WITH_WARNINGS"
        return "PHASE6_SCHEDULED_RUN_COMPLETED"

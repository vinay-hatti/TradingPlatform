from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from .paper_trading_policy import PaperTradingAutomationPolicy
from .paper_trading_profile import (
    PaperTradingCheck,
    PaperTradingRuntimeState,
    PaperTradingSessionDecision,
)


class PaperTradingSessionStateMachine:
    TRANSITIONS: dict[str, dict[str, str]] = {
        "CREATED": {"PREPARE": "READY", "FAIL": "FAILED"},
        "READY": {"START": "RUNNING", "STOP": "STOPPED", "FAIL": "FAILED"},
        "RUNNING": {
            "PAUSE": "PAUSED",
            "STOP": "STOPPING",
            "COMPLETE": "COMPLETED",
            "FAIL": "FAILED",
        },
        "PAUSED": {
            "RESUME": "RUNNING",
            "STOP": "STOPPING",
            "FAIL": "FAILED",
        },
        "STOPPING": {"FINALIZE": "STOPPED", "FAIL": "FAILED"},
        "STOPPED": {},
        "FAILED": {"RECOVER": "READY"},
        "COMPLETED": {},
    }

    def __init__(
        self,
        policy: PaperTradingAutomationPolicy | None = None,
    ) -> None:
        self.policy = policy or PaperTradingAutomationPolicy()
        self.policy.validate()

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95:
            return "A", "LOW"
        if score >= 85:
            return "B", "MODERATE"
        if score >= 70:
            return "C", "SEVERE"
        return "F", "CRITICAL"

    def transition(
        self,
        state: PaperTradingRuntimeState,
        action: str,
    ) -> tuple[PaperTradingSessionDecision, PaperTradingRuntimeState]:
        action = action.strip().upper()
        target = self.TRANSITIONS.get(state.session.state, {}).get(action)
        checks: list[PaperTradingCheck] = []

        def add(name: str, passed: bool, message: str) -> None:
            checks.append(
                PaperTradingCheck(
                    name=name,
                    passed=bool(passed),
                    required=True,
                    score=100.0 if passed else 0.0,
                    severity="LOW" if passed else "CRITICAL",
                    message=message,
                )
            )

        add(
            "transition_defined",
            target is not None,
            "Requested session transition is defined.",
        )
        add(
            "pause_resume_allowed",
            action not in {"PAUSE", "RESUME"}
            or self.policy.allow_pause_resume,
            "Pause/resume is permitted by policy.",
        )
        add(
            "manual_stop_allowed",
            action != "STOP" or self.policy.allow_manual_stop,
            "Manual stop is permitted by policy.",
        )
        add(
            "recovery_allowed",
            action != "RECOVER" or self.policy.allow_restart_recovery,
            "Restart recovery is permitted by policy.",
        )

        failed = [check for check in checks if not check.passed]
        score = (
            sum(check.score for check in checks) / len(checks)
            if checks else 100.0
        )
        allowed = not failed and target is not None
        if not self.policy.fail_closed:
            allowed = target is not None

        grade, severity = self._grade(score)
        decision = PaperTradingSessionDecision(
            valid=True,
            allowed=allowed,
            action=action,
            session_id=state.session.session_id,
            current_state=state.session.state,
            target_state=target,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation="APPLY" if allowed else "REJECT",
            checks=tuple(checks),
            rejection_reasons=tuple(
                check.name.upper() for check in failed
            ),
        )
        if not allowed or target is None:
            return decision, state

        now = datetime.now(timezone.utc).isoformat()
        session_updates = {
            "state": target,
            "started_at": (
                now
                if action == "START" and state.session.started_at is None
                else state.session.started_at
            ),
            "stopped_at": (
                now
                if target in {"STOPPED", "FAILED", "COMPLETED"}
                else state.session.stopped_at
            ),
        }
        session = replace(state.session, **session_updates)
        updated = replace(
            state,
            session=session,
            recovery_required=(target == "FAILED"),
            recovery_reason=(
                "SESSION_FAILED"
                if target == "FAILED"
                else None
                if target == "READY"
                else state.recovery_reason
            ),
            version=state.version + 1,
            updated_at=now,
        )
        return decision, updated

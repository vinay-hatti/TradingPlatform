from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable, Mapping

from .engine import AutomationRecoveryEngine, stable_recovery_id
from .policy import AutomationRecoveryPolicy
from .profile import AutomationRecoveryResult


class AutomationRecoveryService:
    def __init__(
        self,
        policy: AutomationRecoveryPolicy | None = None,
    ) -> None:
        self.policy = policy or AutomationRecoveryPolicy()
        self.policy.validate()
        self.engine = AutomationRecoveryEngine(self.policy)

    def execute(
        self,
        portfolio_id: str,
        scheduler_report: Mapping[str, Any],
        *,
        mode: str = "ANALYZE",
        confirmation: str = "",
        phase_commands: Mapping[int, Iterable[str]] | None = None,
        observability_report: Mapping[str, Any] | None = None,
    ) -> AutomationRecoveryResult:
        run_key = str(scheduler_report.get("run_key") or "UNKNOWN")
        authorization = self.engine.authorize(
            portfolio_id,
            run_key,
            mode=mode,
            confirmation=confirmation,
        )
        checkpoints = self.engine.checkpoints(scheduler_report)
        actions = (
            self.engine.plan(checkpoints, phase_commands=phase_commands)
            if authorization.allowed
            else ()
        )
        verification = self.engine.verification(
            scheduler_report, observability_report
        )
        warnings: list[str] = []
        errors: list[str] = []
        if not authorization.allowed:
            errors.extend(authorization.reason_codes)
            status = "PHASE8_RECOVERY_BLOCKED"
        elif verification["recovery_verified"]:
            status = "PHASE8_RECOVERY_NOT_REQUIRED"
        elif any(not row.safe_to_replay for row in actions):
            status = "PHASE8_MANUAL_RECOVERY_REQUIRED"
            warnings.append("UNSAFE_REPLAY_ACTION_PRESENT")
        elif mode.upper() == "RECOVER":
            status = "PHASE8_RECOVERY_PLAN_AUTHORIZED"
        else:
            status = "PHASE8_RECOVERY_PLAN_READY"

        return AutomationRecoveryResult(
            milestone=51,
            phase=8,
            portfolio_id=portfolio_id,
            source_run_key=run_key,
            recovery_id=stable_recovery_id(portfolio_id, run_key),
            status=status,
            authorization=asdict(authorization),
            checkpoints=tuple(asdict(row) for row in checkpoints),
            actions=tuple(asdict(row) for row in actions),
            verification=verification,
            warnings=tuple(dict.fromkeys(warnings)),
            errors=tuple(dict.fromkeys(errors)),
            metadata={
                "environment": "PAPER",
                "live_trading_enabled": False,
                "automatic_submit_replay": False,
                "action_count": len(actions),
            },
        )

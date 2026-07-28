from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .policy import AutomationRecoveryPolicy
from .profile import RecoveryAction, RecoveryAuthorization, RecoveryCheckpoint


def stable_recovery_id(portfolio_id: str, run_key: str) -> str:
    digest = hashlib.sha256(
        f"{portfolio_id}|{run_key}|RECOVERY".encode()
    ).hexdigest()[:24]
    return f"M51-RECOVERY-{digest.upper()}"


def file_checksum(path: str | Path) -> str:
    value = Path(path)
    if not value.exists() or not value.is_file():
        return ""
    return hashlib.sha256(value.read_bytes()).hexdigest()


class AutomationRecoveryEngine:
    def __init__(
        self,
        policy: AutomationRecoveryPolicy | None = None,
    ) -> None:
        self.policy = policy or AutomationRecoveryPolicy()
        self.policy.validate()

    def authorize(
        self,
        portfolio_id: str,
        run_key: str,
        *,
        mode: str,
        confirmation: str = "",
    ) -> RecoveryAuthorization:
        normalized = mode.upper()
        reasons: list[str] = []
        expected = self.policy.confirmation_template.format(
            portfolio_id=portfolio_id,
            run_key=run_key,
        )
        if normalized not in {"ANALYZE", "RECOVER"}:
            reasons.append("MODE_NOT_ALLOWED")
        if self.policy.live_trading_enabled:
            reasons.append("LIVE_TRADING_ENABLED")
        if self.policy.kill_switch_active and normalized == "RECOVER":
            reasons.append("KILL_SWITCH_ACTIVE")
        if (
            normalized == "RECOVER"
            and self.policy.require_exact_confirmation
            and confirmation != expected
        ):
            reasons.append("CONFIRMATION_MISMATCH")
        return RecoveryAuthorization(
            allowed=not reasons,
            mode=normalized,
            reason_codes=tuple(dict.fromkeys(reasons)),
            required_confirmation=expected if normalized == "RECOVER" else "",
            kill_switch_active=self.policy.kill_switch_active,
            live_trading_enabled=self.policy.live_trading_enabled,
            metadata={"environment": self.policy.environment},
        )

    def checkpoints(
        self,
        scheduler_report: Mapping[str, Any],
    ) -> tuple[RecoveryCheckpoint, ...]:
        run_key = str(scheduler_report.get("run_key") or "UNKNOWN")
        output: list[RecoveryCheckpoint] = []
        for row in scheduler_report.get("executions") or ():
            metadata = dict(row.get("metadata") or {})
            report_path = str(row.get("report_path") or metadata.get("report_path") or "")
            checksum = file_checksum(report_path) if report_path else ""
            status = str(row.get("status") or "UNKNOWN")
            output.append(
                RecoveryCheckpoint(
                    checkpoint_id=f"{run_key}-PHASE-{row.get('phase')}",
                    run_key=run_key,
                    phase=int(row.get("phase") or 0),
                    status=status,
                    completed=status == "COMPLETED",
                    report_path=report_path,
                    checksum=checksum,
                    metadata={
                        "attempt_count": int(row.get("attempt_count") or 0),
                        "exit_code": row.get("exit_code"),
                        "required": bool(metadata.get("required", True)),
                    },
                )
            )
        return tuple(sorted(output, key=lambda item: item.phase))

    def plan(
        self,
        checkpoints: Iterable[RecoveryCheckpoint],
        *,
        phase_commands: Mapping[int, Iterable[str]] | None = None,
    ) -> tuple[RecoveryAction, ...]:
        commands = phase_commands or {}
        rows = tuple(checkpoints)
        actions: list[RecoveryAction] = []
        sequence = 1

        failed_or_incomplete = [
            row for row in rows if not row.completed or row.status == "FAILED"
        ]
        if not failed_or_incomplete:
            actions.append(
                RecoveryAction(
                    sequence=sequence,
                    action_code="NO_REPLAY_REQUIRED",
                    phase=None,
                    action="VERIFY_COMPLETED_RUN",
                    reason="all recorded phases completed",
                    safe_to_replay=True,
                    requires_confirmation=False,
                )
            )
            sequence += 1
        else:
            start_phase = min(row.phase for row in failed_or_incomplete)
            for row in rows:
                if row.phase < start_phase:
                    continue
                safe = row.phase in {2, 4, 5, 7}
                action_code = (
                    "REPLAY_MONITOR_OR_REPORT"
                    if safe
                    else "MANUAL_REVIEW_REQUIRED"
                )
                actions.append(
                    RecoveryAction(
                        sequence=sequence,
                        action_code=action_code,
                        phase=row.phase,
                        action=(
                            "REPLAY_PHASE"
                            if safe
                            else "REVIEW_BEFORE_REPLAY"
                        ),
                        reason=(
                            f"phase {row.phase} is incomplete or follows "
                            f"the first failed phase {start_phase}"
                        ),
                        safe_to_replay=safe,
                        requires_confirmation=not safe,
                        command=tuple(str(v) for v in commands.get(row.phase, ())),
                        metadata={"source_status": row.status},
                    )
                )
                sequence += 1

        if self.policy.require_control_plane_revalidation:
            actions.append(
                RecoveryAction(
                    sequence=sequence,
                    action_code="REVALIDATE_CONTROL_PLANE",
                    phase=5,
                    action="RUN_PHASE5_DRY_RUN",
                    reason="recovery must re-evaluate portfolio and routing gates",
                    safe_to_replay=True,
                    requires_confirmation=False,
                    command=tuple(str(v) for v in commands.get(5, ())),
                )
            )
            sequence += 1
        if self.policy.require_post_recovery_observability:
            actions.append(
                RecoveryAction(
                    sequence=sequence,
                    action_code="VERIFY_OBSERVABILITY",
                    phase=7,
                    action="RUN_PHASE7_HEALTH_CHECK",
                    reason="post-recovery health must be verified",
                    safe_to_replay=True,
                    requires_confirmation=False,
                    command=tuple(str(v) for v in commands.get(7, ())),
                )
            )
        return tuple(actions)

    def verification(
        self,
        scheduler_report: Mapping[str, Any],
        observability_report: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        scheduler_status = str(scheduler_report.get("status") or "UNKNOWN")
        observable = observability_report or {}
        health_status = str(observable.get("overall_status") or "NOT_PROVIDED")
        incidents = len(observable.get("incidents") or ())
        scheduler_ok = scheduler_status in {
            "PHASE6_SCHEDULED_RUN_COMPLETED",
            "PHASE6_SCHEDULED_RUN_COMPLETED_WITH_WARNINGS",
        }
        observability_ok = (
            not self.policy.require_post_recovery_observability
            or health_status == "PHASE7_AUTOMATION_HEALTHY"
        )
        return {
            "scheduler_status": scheduler_status,
            "scheduler_completed": scheduler_ok,
            "observability_status": health_status,
            "observability_healthy": observability_ok,
            "incident_count": incidents,
            "recovery_verified": scheduler_ok and observability_ok,
        }

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .m32_phase5_profile import DisasterRecoveryExercise


def _iso(value: datetime | str) -> str:
    if isinstance(value, str):
        return value
    current = value
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat()


def _minutes(started_at: datetime | str, completed_at: datetime | str) -> float:
    start = (
        datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        if isinstance(started_at, str)
        else started_at
    )
    end = (
        datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        if isinstance(completed_at, str)
        else completed_at
    )
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return max(0.0, (end - start).total_seconds() / 60.0)


class DisasterRecoveryExerciseService:
    """Builds governed DR exercise evidence without executing destructive actions."""

    def record(
        self,
        *,
        exercise_id: str,
        plan: Any,
        scenario: str,
        started_at: datetime | str,
        completed_at: datetime | str,
        observed_rpo_minutes: float,
        backup_verified: bool,
        restore_verified: bool,
        failover_verified: bool,
        failback_verified: bool,
        evidence: tuple[str, ...],
        notes: str = "",
    ) -> DisasterRecoveryExercise:
        if observed_rpo_minutes < 0:
            raise ValueError("observed_rpo_minutes cannot be negative")
        if not exercise_id.strip():
            raise ValueError("exercise_id is required")
        if not scenario.strip():
            raise ValueError("scenario is required")

        plan_id = getattr(plan, "dr_plan_id", None) or getattr(
            plan, "plan_id", None
        )
        if not plan_id:
            raise ValueError("DR plan identifier is required")

        target_rto = int(getattr(plan, "rto_minutes"))
        target_rpo = int(getattr(plan, "rpo_minutes"))
        observed_rto = _minutes(started_at, completed_at)

        return DisasterRecoveryExercise(
            exercise_id=exercise_id,
            plan_id=str(plan_id),
            scenario=scenario,
            started_at=_iso(started_at),
            completed_at=_iso(completed_at),
            target_rto_minutes=target_rto,
            observed_rto_minutes=observed_rto,
            target_rpo_minutes=target_rpo,
            observed_rpo_minutes=float(observed_rpo_minutes),
            backup_verified=backup_verified,
            restore_verified=restore_verified,
            failover_verified=failover_verified,
            failback_verified=failback_verified,
            evidence=tuple(evidence),
            notes=notes,
        )

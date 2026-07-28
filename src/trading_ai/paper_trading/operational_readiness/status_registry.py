from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class PhaseStatusDisposition:
    phase: int
    status: str
    disposition: str
    reason: str


class PhaseStatusRegistry:
    """Classifies phase statuses without hard-coding only one exact output set.

    Dispositions:
      PASS  - healthy, completed, synchronized, ready, no-work, or controlled idle.
      WARN  - valid but attention-worthy, such as blocked/manual/degraded states.
      FAIL  - explicit failure, error, corruption, unsafe, or rejected state.
    """

    EXPLICIT_PASS: Mapping[int, frozenset[str]] = {
        1: frozenset({
            "PHASE1_AUTOMATION_READY",
            "PHASE1_DRY_RUN_COMPLETED",
            "PHASE1_ORDERS_READY",
            "PHASE1_AUTOMATED_PAPER_HANDOFF_COMPLETED",
        }),
        2: frozenset({
            "PHASE2_LIFECYCLE_HEALTHY",
            "PHASE2_MONITOR_COMPLETED",
            "PHASE2_LIFECYCLE_SYNCHRONIZED",
            "NO_ACTIVE_ORDERS",
        }),
        3: frozenset({
            "PHASE3_POSITIONS_MONITORED",
            "PHASE3_EXIT_ACTIONS_READY",
            "NO_OPEN_POSITIONS",
        }),
        4: frozenset({
            "PHASE4_PORTFOLIO_HEALTHY",
            "PHASE4_NO_OPEN_POSITIONS",
        }),
        5: frozenset({
            "PHASE5_AUTOMATION_READY",
            "PHASE5_AUTOMATION_READY_WITH_WARNINGS",
            "PHASE5_AUTOMATED_PAPER_CYCLE_AUTHORIZED",
        }),
        6: frozenset({
            "PHASE6_SCHEDULED_RUN_COMPLETED",
            "PHASE6_SCHEDULED_RUN_COMPLETED_WITH_WARNINGS",
        }),
        7: frozenset({
            "PHASE7_AUTOMATION_HEALTHY",
            "PHASE7_AUTOMATION_DEGRADED",
        }),
        8: frozenset({
            "PHASE8_RECOVERY_NOT_REQUIRED",
            "PHASE8_RECOVERY_PLAN_READY",
            "PHASE8_RECOVERY_PLAN_AUTHORIZED",
        }),
    }

    CONTROLLED_WARNING_TOKENS = (
        "BLOCKED",
        "IDLE",
        "MANUAL",
        "DEGRADED",
        "AWAITING",
        "PENDING_CONFIRMATION",
        "NO_ACTION_REQUIRED",
        "NOT_REQUIRED",
    )
    FAILURE_TOKENS = (
        "FAILED",
        "FAILURE",
        "ERROR",
        "CORRUPT",
        "UNSAFE",
        "REJECTED",
        "FATAL",
    )
    WARNING_TOKENS = (
        "UNHEALTHY",
        "DEGRADED",
        "BLOCKED",
        "IDLE",
        "MANUAL",
        "AWAITING",
        "PENDING_CONFIRMATION",
        "NO_ACTION_REQUIRED",
        "NOT_REQUIRED",
    )
    PASS_TOKENS = (
        "COMPLETED",
        "READY",
        "HEALTHY",
        "SYNCHRONIZED",
        "AUTHORIZED",
        "MONITORED",
        "NO_OPEN",
        "NO_ACTIVE",
    )

    def classify(self, phase: int, status: str) -> PhaseStatusDisposition:
        normalized = (status or "UNKNOWN").strip().upper()

        if normalized in self.EXPLICIT_PASS.get(phase, frozenset()):
            return PhaseStatusDisposition(
                phase=phase,
                status=normalized,
                disposition="PASS",
                reason="EXPLICIT_ACCEPTED_STATUS",
            )

        if any(token in normalized for token in self.FAILURE_TOKENS):
            return PhaseStatusDisposition(
                phase=phase,
                status=normalized,
                disposition="FAIL",
                reason="EXPLICIT_FAILURE_SEMANTICS",
            )

        # Evaluate negative/attention semantics before positive semantics.
        # This prevents HEALTHY from matching inside UNHEALTHY.
        if any(token in normalized for token in self.WARNING_TOKENS):
            return PhaseStatusDisposition(
                phase=phase,
                status=normalized,
                disposition="WARN",
                reason="CONTROLLED_NON_TERMINAL_OR_ATTENTION_STATE",
            )

        if any(token in normalized for token in self.PASS_TOKENS):
            return PhaseStatusDisposition(
                phase=phase,
                status=normalized,
                disposition="PASS",
                reason="ACCEPTED_STATUS_SEMANTICS",
            )

        return PhaseStatusDisposition(
            phase=phase,
            status=normalized,
            disposition="WARN",
            reason="UNKNOWN_STATUS_REQUIRES_REVIEW",
        )

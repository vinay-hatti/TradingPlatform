from __future__ import annotations

from datetime import datetime, timezone

from .operational_governance_policy import OperationalGovernancePolicy
from .operational_governance_profile import (
    GovernanceFinding,
    OperationalRunbook,
)


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class OperationalRunbookService:
    def __init__(
        self,
        policy: OperationalGovernancePolicy | None = None,
    ) -> None:
        self.policy = policy or OperationalGovernancePolicy()
        self.policy.validate()

    def evaluate(
        self,
        runbook: OperationalRunbook | None,
        *,
        as_of: datetime | None = None,
    ) -> tuple[bool, float, tuple[GovernanceFinding, ...]]:
        findings: list[GovernanceFinding] = []
        if runbook is None:
            findings.append(
                GovernanceFinding(
                    finding_id="runbook-missing",
                    category="RUNBOOK",
                    severity="CRITICAL",
                    status="OPEN",
                    summary="Operational runbook is missing.",
                    recommendation="Create and approve a production runbook.",
                )
            )
            return False, 0.0, tuple(findings)

        now = as_of or datetime.now(timezone.utc)
        checks: list[bool] = []

        checks.append(bool(runbook.owner))
        if not runbook.owner:
            findings.append(self._finding(
                "runbook-owner", "HIGH",
                "Runbook owner is missing.",
                "Assign an accountable service owner.",
            ))

        checks.append(bool(runbook.reviewer))
        if not runbook.reviewer:
            findings.append(self._finding(
                "runbook-reviewer", "HIGH",
                "Runbook reviewer is missing.",
                "Assign an independent reviewer.",
            ))

        age_days = (now - _parse(runbook.last_reviewed_at)).days
        current = age_days <= self.policy.maximum_runbook_age_days
        checks.append(current)
        if not current:
            findings.append(self._finding(
                "runbook-stale", "HIGH",
                f"Runbook review is {age_days} days old.",
                "Review and reapprove the runbook.",
            ))

        has_steps = bool(runbook.steps)
        checks.append(has_steps)
        if not has_steps:
            findings.append(self._finding(
                "runbook-steps", "CRITICAL",
                "Runbook has no executable steps.",
                "Add ordered actions and validation criteria.",
            ))

        ordered = tuple(
            step.sequence for step in runbook.steps
        ) == tuple(sorted(step.sequence for step in runbook.steps))
        checks.append(ordered)
        if not ordered:
            findings.append(self._finding(
                "runbook-order", "MEDIUM",
                "Runbook steps are not ordered.",
                "Use a deterministic sequence.",
            ))

        escalation = bool(runbook.escalation_path)
        checks.append(escalation)
        if not escalation:
            findings.append(self._finding(
                "runbook-escalation", "HIGH",
                "Incident escalation path is missing.",
                "Add on-call and management escalation contacts.",
            ))

        score = sum(checks) / len(checks)
        ready = all(checks)
        return ready, score, tuple(findings)

    @staticmethod
    def _finding(
        suffix: str,
        severity: str,
        summary: str,
        recommendation: str,
    ) -> GovernanceFinding:
        return GovernanceFinding(
            finding_id=f"runbook-{suffix}",
            category="RUNBOOK",
            severity=severity,
            status="OPEN",
            summary=summary,
            recommendation=recommendation,
        )

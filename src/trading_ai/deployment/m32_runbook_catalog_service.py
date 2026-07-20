from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .operational_runbook_service import OperationalRunbookService
from .m32_phase5_profile import RunbookCertification


class OperationalRunbookCatalogService:
    REQUIRED_RUNBOOK_TYPES = (
        "STARTUP",
        "SHUTDOWN",
        "INCIDENT_RESPONSE",
        "MARKET_DATA_FAILURE",
        "BROKER_FAILURE",
        "DATABASE_RECOVERY",
        "DISASTER_RECOVERY",
        "SECURITY_INCIDENT",
    )

    def __init__(
        self,
        evaluator: OperationalRunbookService | None = None,
    ) -> None:
        self.evaluator = evaluator or OperationalRunbookService()

    def certify(
        self,
        runbooks: tuple[Any, ...],
        *,
        as_of: datetime | None = None,
    ) -> tuple[RunbookCertification, ...]:
        certifications = []
        now = as_of or datetime.now(timezone.utc)
        for runbook in runbooks:
            ready, score, findings = self.evaluator.evaluate(
                runbook,
                as_of=now,
            )
            certifications.append(
                RunbookCertification(
                    runbook_id=runbook.runbook_id,
                    name=runbook.name,
                    ready=ready,
                    score=score,
                    findings=tuple(
                        {
                            "finding_id": finding.finding_id,
                            "category": finding.category,
                            "severity": finding.severity,
                            "status": finding.status,
                            "summary": finding.summary,
                            "recommendation": finding.recommendation,
                        }
                        for finding in findings
                    ),
                )
            )
        return tuple(certifications)

    def write_standard_runbooks(
        self,
        target_directory: str | Path,
    ) -> tuple[Path, ...]:
        root = Path(target_directory)
        root.mkdir(parents=True, exist_ok=True)
        generated = []
        for runbook_type in self.REQUIRED_RUNBOOK_TYPES:
            path = root / f"{runbook_type.lower()}_runbook.md"
            title = runbook_type.replace("_", " ").title()
            path.write_text(
                self._template(title, runbook_type),
                encoding="utf-8",
            )
            generated.append(path)
        return tuple(generated)

    @staticmethod
    def _template(title: str, runbook_type: str) -> str:
        return f"""# {title} Runbook

## Governance

- Runbook type: `{runbook_type}`
- Environment: Production/Paper
- Owner: Assign accountable service owner
- Reviewer: Assign independent reviewer
- Review frequency: Quarterly
- Live trading default: Disabled

## Preconditions

1. Confirm operator identity and authorization.
2. Record incident or change identifier.
3. Confirm current environment and active release.
4. Confirm backup and rollback availability.
5. Confirm risk kill switch state.

## Procedure

1. Capture current health, readiness, metrics, and alerts.
2. Execute the approved operational action.
3. Validate market data, broker, database, risk, and execution state.
4. Reconcile orders, fills, positions, and portfolio risk.
5. Confirm audit evidence was written.
6. Escalate on any failed validation.

## Rollback / Recovery

1. Stop new order generation.
2. Activate the risk kill switch when required.
3. Restore the last validated configuration or release.
4. Reconcile persistent state.
5. Run smoke and readiness checks.
6. Obtain incident commander approval before resuming.

## Evidence

- Command transcript
- Structured logs
- Metrics snapshot
- Reconciliation report
- Approval record
- Incident/change ticket

## Completion Criteria

- All required checks pass.
- No unresolved critical or high findings.
- Audit evidence is complete.
- Service owner and reviewer sign off.
"""

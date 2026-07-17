from __future__ import annotations

from collections import defaultdict

from .operational_governance_policy import OperationalGovernancePolicy
from .operational_governance_profile import (
    ComplianceControl,
    ComplianceEvidence,
    GovernanceFinding,
)


class ComplianceGovernanceService:
    def __init__(
        self,
        policy: OperationalGovernancePolicy | None = None,
    ) -> None:
        self.policy = policy or OperationalGovernancePolicy()
        self.policy.validate()

    def evaluate(
        self,
        controls: tuple[ComplianceControl, ...],
        evidence: tuple[ComplianceEvidence, ...],
    ) -> tuple[bool, float, tuple[GovernanceFinding, ...]]:
        by_control: dict[str, list[ComplianceEvidence]] = defaultdict(list)
        for item in evidence:
            by_control[item.control_id].append(item)

        findings: list[GovernanceFinding] = []
        weighted_total = 0.0
        weighted_pass = 0.0

        severity_weight = {
            "CRITICAL": 4.0,
            "HIGH": 3.0,
            "MEDIUM": 2.0,
            "LOW": 1.0,
        }

        for control in controls:
            weight = severity_weight.get(control.severity.upper(), 1.0)
            if not control.required:
                weight *= 0.5
            weighted_total += weight

            valid_evidence = [
                item for item in by_control.get(control.control_id, ())
                if item.valid
            ]
            required_types = set(control.evidence_types)
            provided_types = {
                item.evidence_type for item in valid_evidence
            }

            passed = bool(valid_evidence)
            if required_types:
                passed = required_types.issubset(provided_types)

            if passed:
                weighted_pass += weight
            else:
                findings.append(
                    GovernanceFinding(
                        finding_id=f"compliance-{control.control_id}",
                        category="COMPLIANCE",
                        severity=control.severity,
                        status="OPEN",
                        summary=(
                            f"Control {control.control_id} lacks valid "
                            "required evidence."
                        ),
                        recommendation=(
                            "Collect and validate the required evidence: "
                            + ", ".join(control.evidence_types)
                        ),
                        evidence={
                            "framework": control.framework,
                            "provided_types": sorted(provided_types),
                        },
                    )
                )

        score = (
            weighted_pass / weighted_total
            if weighted_total > 0 else 1.0
        )
        critical_open = sum(
            finding.severity.upper() == "CRITICAL"
            for finding in findings
        )
        ready = (
            score >= self.policy.minimum_compliance_score
            and critical_open
            <= self.policy.maximum_unresolved_critical_findings
        )
        return ready, score, tuple(findings)

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .knowledge_dashboard_policy import KnowledgeDashboardPolicy
from .knowledge_dashboard_profile import (
    DashboardMetricProfile,
    KnowledgeDashboardProfile,
)


class KnowledgeDashboardEngine:
    def __init__(self, policy: KnowledgeDashboardPolicy | None = None) -> None:
        self.policy = policy or KnowledgeDashboardPolicy()
        self.policy.validate()

    @staticmethod
    def _get(source: Any, name: str, default: Any = None) -> Any:
        if isinstance(source, Mapping):
            return source.get(name, default)
        return getattr(source, name, default)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 0.93:
            return "A+"
        if score >= 0.88:
            return "A"
        if score >= 0.84:
            return "A-"
        if score >= 0.80:
            return "B+"
        if score >= 0.75:
            return "B"
        if score >= 0.70:
            return "B-"
        if score >= 0.60:
            return "C"
        return "NOT_READY"

    def build(
        self,
        *,
        knowledge_base: Any,
        pattern_discovery: Any,
        institutional_learning: Any,
        analyst_performance: Any,
        dashboard_id: str = "M34-PHASE5-KNOWLEDGE-DASHBOARD-001",
        generated_at: datetime | None = None,
    ) -> KnowledgeDashboardProfile:
        cases = tuple(self._get(knowledge_base, "cases", ()) or ())
        clusters = tuple(self._get(pattern_discovery, "clusters", ()) or ())
        learning_cases = int(
            self._get(
                institutional_learning,
                "case_count",
                self._get(institutional_learning, "cases_learned", len(cases)),
            )
            or 0
        )
        scorecards = tuple(self._get(analyst_performance, "scorecards", ()) or ())

        knowledge_score = self._clamp(min(1.0, len(cases) / 10.0))
        pattern_score = self._clamp(min(1.0, len(clusters) / 5.0))
        learning_score = self._clamp(min(1.0, learning_cases / 10.0))
        analyst_score = self._clamp(
            sum(float(self._get(card, "composite_score", 0.0) or 0.0) for card in scorecards)
            / len(scorecards)
            if scorecards
            else 0.0
        )

        statuses = {
            "knowledge_base": str(self._get(knowledge_base, "governance_status", "READY")),
            "pattern_discovery": str(self._get(pattern_discovery, "governance_status", "READY")),
            "institutional_learning": str(self._get(institutional_learning, "governance_status", "READY")),
            "analyst_performance": str(self._get(analyst_performance, "governance_status", "READY")),
        }
        ready_sources = sum(1 for value in statuses.values() if value == "READY")
        governance_score = ready_sources / len(statuses)

        readiness = (
            self.policy.knowledge_weight * knowledge_score
            + self.policy.pattern_weight * pattern_score
            + self.policy.learning_weight * learning_score
            + self.policy.analyst_weight * analyst_score
            + self.policy.governance_weight * governance_score
        )
        readiness = self._clamp(readiness)

        metrics = (
            DashboardMetricProfile(
                name="Knowledge Quality",
                value=round(knowledge_score, 6),
                status="READY" if knowledge_score >= 0.5 else "DEVELOPING",
                detail=f"{len(cases)} research case(s) available.",
            ),
            DashboardMetricProfile(
                name="Pattern Confidence",
                value=round(pattern_score, 6),
                status="READY" if pattern_score >= 0.5 else "DEVELOPING",
                detail=f"{len(clusters)} pattern cluster(s) available.",
            ),
            DashboardMetricProfile(
                name="Learning Maturity",
                value=round(learning_score, 6),
                status="READY" if learning_score >= 0.5 else "DEVELOPING",
                detail=f"{learning_cases} case(s) incorporated into learning.",
            ),
            DashboardMetricProfile(
                name="Analyst Discipline",
                value=round(analyst_score, 6),
                status="READY" if analyst_score >= 0.7 else "DEVELOPING",
                detail=f"{len(scorecards)} analyst scorecard(s) available.",
            ),
            DashboardMetricProfile(
                name="Governance",
                value=round(governance_score, 6),
                status="READY" if governance_score == 1.0 else "REVIEW",
                detail=f"{ready_sources} of {len(statuses)} source domains ready.",
            ),
        )

        highlights = [
            f"Research knowledge base contains {len(cases)} case(s).",
            f"Pattern discovery produced {len(clusters)} cluster(s).",
            f"Institutional learning incorporated {learning_cases} case(s).",
            f"Analyst performance includes {len(scorecards)} scorecard(s).",
        ]
        risks = []
        if len(cases) < 3:
            risks.append("Research history remains limited.")
        if len(clusters) == 0:
            risks.append("No stable pattern clusters are available.")
        if not scorecards:
            risks.append("No analyst scorecards are available.")
        if governance_score < 1.0:
            risks.append("One or more source domains require governance review.")
        if not risks:
            risks.append("No material phase-closure risks detected.")

        governance_status = (
            "READY"
            if readiness >= self.policy.ready_threshold and governance_score == 1.0
            else "REVIEW"
        )

        return KnowledgeDashboardProfile(
            dashboard_id=dashboard_id,
            generated_at=generated_at or datetime.now(timezone.utc),
            milestone=34,
            phase=5,
            research_case_count=len(cases),
            pattern_cluster_count=len(clusters),
            institutional_learning_case_count=learning_cases,
            analyst_count=len(scorecards),
            governance_status=governance_status,
            readiness_score=round(readiness, 6),
            readiness_grade=self._grade(readiness),
            metrics=metrics,
            highlights=tuple(highlights),
            risks=tuple(risks),
            source_status=statuses,
            metadata={
                "milestone_complete": governance_status == "READY",
                "phase_complete": governance_status == "READY",
            },
        )

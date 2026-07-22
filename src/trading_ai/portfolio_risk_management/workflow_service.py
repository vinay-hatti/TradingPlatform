from __future__ import annotations

from pathlib import Path
from typing import Any

from .policy import PortfolioRiskPolicy
from .profile import utc_now_iso
from .reporting_service import PortfolioRiskReportingService
from .repository import PortfolioRiskRepository
from .serialization import write_json_atomic
from .service import PortfolioRiskManagementService


class Milestone37WorkflowService:
    def __init__(self, policy: PortfolioRiskPolicy | None = None) -> None:
        self.policy = policy or PortfolioRiskPolicy()

    def run(self, registry_file: Path, output_dir: Path) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        service = PortfolioRiskManagementService(self.policy)
        assessment = service.assess(registry_file, output_dir / "latest_assessment.json")
        repository = PortfolioRiskRepository(
            output_dir / "risk_assessment_history.json",
            output_dir / "risk_breaches.json",
            output_dir / "remediation_actions.json",
        )
        persistence = repository.persist(assessment)
        PortfolioRiskReportingService().write(
            assessment, self.policy,
            output_dir / "milestone37_closure.json",
            output_dir / "milestone37_closure.html",
        )
        handoff = {
            "generated_at": utc_now_iso(),
            "portfolio_id": assessment.portfolio_id,
            "risk_assessment_id": assessment.assessment_id,
            "risk_status": assessment.status,
            "trading_control": assessment.trading_control,
            "allow_new_risk": assessment.trading_control in {"ALLOW", "ALLOW_WITH_WARNING"},
            "reduce_only": assessment.trading_control == "REDUCE_ONLY",
            "blocking_breach_ids": [b.breach_id for b in assessment.breaches if b.severity == "CRITICAL"],
            "recommendations": list(assessment.recommendations),
        }
        write_json_atomic(output_dir / "execution_risk_control.json", handoff)
        result = {
            "milestone": 37,
            "status": "COMPLETE",
            "portfolio_id": assessment.portfolio_id,
            "risk_status": assessment.status,
            "trading_control": assessment.trading_control,
            "assessment_id": assessment.assessment_id,
            "breach_count": len(assessment.breaches),
            "stress_scenario_count": len(assessment.stress_results),
            "persistence": persistence,
            "outputs": {
                "assessment": str(output_dir / "latest_assessment.json"),
                "closure_json": str(output_dir / "milestone37_closure.json"),
                "closure_html": str(output_dir / "milestone37_closure.html"),
                "execution_control": str(output_dir / "execution_risk_control.json"),
            },
        }
        write_json_atomic(output_dir / "workflow_result.json", result)
        return result

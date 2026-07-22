from __future__ import annotations

from sqlalchemy.orm import Session

from .database_models import PortfolioRiskAssessmentModel, PortfolioRiskBreachModel, PortfolioStressResultModel
from .profile import PortfolioRiskAssessment


class PortfolioRiskDatabaseService:
    def synchronize(self, session: Session, assessment: PortfolioRiskAssessment) -> dict[str, int]:
        session.merge(PortfolioRiskAssessmentModel(
            assessment_id=assessment.assessment_id,
            portfolio_id=assessment.portfolio_id,
            generated_at=assessment.generated_at,
            status=assessment.status,
            trading_control=assessment.trading_control,
            net_liquidation_value=assessment.net_liquidation_value,
            cash_balance=assessment.cash_balance,
            capital_committed=assessment.capital_committed,
            open_position_count=assessment.open_position_count,
            payload_json=assessment.to_dict(),
        ))
        for breach in assessment.breaches:
            session.merge(PortfolioRiskBreachModel(
                breach_id=breach.breach_id,
                assessment_id=assessment.assessment_id,
                portfolio_id=assessment.portfolio_id,
                code=breach.code,
                severity=breach.severity,
                status=breach.status,
                observed_value=breach.observed_value,
                limit_value=breach.limit_value,
                recommended_action=breach.recommended_action,
                message=breach.message,
                created_at=breach.created_at,
                resolved_at=None,
                resolution=None,
            ))
        for result in assessment.stress_results:
            session.merge(PortfolioStressResultModel(
                result_id=f"{assessment.assessment_id}:{result.scenario_id}",
                assessment_id=assessment.assessment_id,
                portfolio_id=assessment.portfolio_id,
                scenario_id=result.scenario_id,
                estimated_pnl=result.estimated_pnl,
                estimated_loss_pct_nav=result.estimated_loss_pct_nav,
                status=result.status,
                payload_json=result.to_dict(),
            ))
        session.commit()
        return {
            "assessments_upserted": 1,
            "breaches_upserted": len(assessment.breaches),
            "stress_results_upserted": len(assessment.stress_results),
        }

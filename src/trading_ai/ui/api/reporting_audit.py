from fastapi import APIRouter, Depends

from trading_ai.ui.models.reporting_audit import ReportingAuditResponse
from trading_ai.ui.services.reporting_audit_service import ReportingAuditService

router = APIRouter(prefix="/api/v1", tags=["reporting-audit"])


def service() -> ReportingAuditService:
    return ReportingAuditService()


@router.get("/reporting-audit", response_model=ReportingAuditResponse)
def reporting_audit(
    center: ReportingAuditService = Depends(service),
):
    return center.get()

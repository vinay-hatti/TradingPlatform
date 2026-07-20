from fastapi import APIRouter, Depends

from trading_ai.ui.models.executive_reporting import RegulatoryExportRequest
from trading_ai.ui.services.executive_reporting_service import ExecutiveReportingService

router = APIRouter(prefix="/api/v1/executive", tags=["executive-reporting"])

def service():
    return ExecutiveReportingService()

@router.get("/scorecard")
def scorecard(svc=Depends(service)):
    return svc.scorecard()

@router.get("/board-report")
def board_report(svc=Depends(service)):
    return svc.board_report()

@router.post("/regulatory-exports")
def regulatory_export(request: RegulatoryExportRequest, svc=Depends(service)):
    return svc.regulatory_export(request)

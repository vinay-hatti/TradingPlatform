from fastapi import APIRouter, HTTPException
from trading_ai.ui.models.research_scanner import ResearchScannerRequest, ResearchScannerResponse
from trading_ai.ui.services.research_scanner_service import ResearchScannerDashboardService

router = APIRouter(prefix="/api/research-scanner", tags=["research-scanner"])
_service = ResearchScannerDashboardService()

@router.get("/health")
def health():
    return {"status": "ok", "component": "institutional-research-scanner", "milestone": "34", "phase": "1"}

@router.post("/scan", response_model=ResearchScannerResponse)
def scan(request: ResearchScannerRequest):
    try:
        return _service.execute(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Research scanner failed: {exc}") from exc

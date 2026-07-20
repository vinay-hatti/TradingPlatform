from fastapi import APIRouter, Depends

from trading_ai.ui.services.ui_resilience_service import UiResilienceService

router = APIRouter(prefix="/api/v1/ui-resilience", tags=["ui-resilience"])

def service():
    return UiResilienceService()

@router.get("/manifest")
def manifest(svc=Depends(service)):
    return svc.manifest()

@router.get("/diagnostics")
def diagnostics(svc=Depends(service)):
    return svc.diagnostics()

from fastapi import APIRouter, Depends
from trading_ai.ui.models.admin_runtime import AdminRuntimeResponse, RuntimeControlRequest, RuntimeControlResult
from trading_ai.ui.services.admin_runtime_service import AdminRuntimeService

router = APIRouter(prefix="/api/v1/admin-runtime", tags=["admin-runtime"])
def service(): return AdminRuntimeService()

@router.get("", response_model=AdminRuntimeResponse)
def admin_runtime(center: AdminRuntimeService = Depends(service)):
    return center.get()

@router.post("/controls/{action}/{target}", response_model=RuntimeControlResult)
def runtime_control(action: str, target: str, request: RuntimeControlRequest, center: AdminRuntimeService = Depends(service)):
    return center.control(action, target, request)

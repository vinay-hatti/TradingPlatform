from fastapi import APIRouter, Depends

from trading_ai.ui.models.workstation_release import WorkstationReleaseResponse
from trading_ai.ui.services.workstation_release_service import (
    WorkstationReleaseService,
)

router = APIRouter(prefix="/api/v1/workstation-release", tags=["workstation-release"])


def service() -> WorkstationReleaseService:
    return WorkstationReleaseService()


@router.get("", response_model=WorkstationReleaseResponse)
def workstation_release(
    center: WorkstationReleaseService = Depends(service),
):
    return center.get()

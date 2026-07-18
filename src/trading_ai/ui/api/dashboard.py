from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from trading_ai.ui.models.dashboard import DashboardSnapshot
from trading_ai.ui.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


def get_dashboard_service() -> DashboardService:
    return DashboardService()


@router.get("/dashboard", response_model=DashboardSnapshot)
def dashboard(
    include_raw: bool = Query(
        default=False,
        description="Include internal adapter diagnostics and artifact paths.",
    ),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardSnapshot:
    snapshot = service.snapshot()
    if not include_raw:
        snapshot.raw = {}
    return snapshot

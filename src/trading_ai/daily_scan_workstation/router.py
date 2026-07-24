from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from trading_ai.production_api.models import ApiEnvelope
from trading_ai.production_api.security import require_access, require_mutation_access

from .models import DataRefreshRequest, DailyScanRequest
from .service import DailyScanWorkstationService

router = APIRouter(prefix="/api/v1/scanner", tags=["daily-scanner"])


def service(request: Request) -> DailyScanWorkstationService:
    return request.app.state.m43_service


def envelope(request: Request, data, **metadata) -> ApiEnvelope:
    return ApiEnvelope(request_id=request.state.request_id, data=data, metadata=metadata)




@router.get("/universes", response_model=ApiEnvelope)
def list_scanner_universes(request: Request, _: str = Depends(require_access)):
    from trading_ai.market.universe import list_universes

    return envelope(request, list(list_universes()))


@router.get("/runs", response_model=ApiEnvelope)
def list_runs(request: Request, limit: int = Query(default=30, ge=1, le=200), _: str = Depends(require_access), svc: DailyScanWorkstationService = Depends(service)):
    return envelope(request, [run.model_dump(mode="json") for run in svc.list_runs(limit)])


@router.get("/runs/{run_id}", response_model=ApiEnvelope)
def get_run(run_id: str, request: Request, _: str = Depends(require_access), svc: DailyScanWorkstationService = Depends(service)):
    try:
        run = svc.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Scanner run not found") from exc
    return envelope(request, run.model_dump(mode="json"))


@router.get("/runs/{run_id}/results", response_model=ApiEnvelope)
def get_results(run_id: str, request: Request, _: str = Depends(require_access), svc: DailyScanWorkstationService = Depends(service)):
    try:
        return envelope(request, svc.results(run_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Scanner run not found") from exc


@router.post("/data-refresh", response_model=ApiEnvelope, status_code=202)
def refresh_data(payload: DataRefreshRequest, request: Request, actor: str = Depends(require_mutation_access), svc: DailyScanWorkstationService = Depends(service)):
    run = svc.start_refresh(payload, actor)
    return envelope(request, run.model_dump(mode="json"), actor=actor)


@router.post("/runs", response_model=ApiEnvelope, status_code=202)
def start_scan(payload: DailyScanRequest, request: Request, actor: str = Depends(require_mutation_access), svc: DailyScanWorkstationService = Depends(service)):
    run = svc.start_scan(payload, actor)
    return envelope(request, run.model_dump(mode="json"), actor=actor)

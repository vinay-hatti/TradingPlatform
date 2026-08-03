from __future__ import annotations

from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from .models import ApiEnvelope, WorkflowRunRequest, WorkflowRunResult
from .security import require_access, require_mutation_access
from .service import ProductionApiService

router = APIRouter(prefix="/api/v1/platform", tags=["production-platform"])


def service(request: Request) -> ProductionApiService:
    return request.app.state.m40_service


def envelope(request: Request, data, **metadata) -> ApiEnvelope:
    return ApiEnvelope(request_id=request.state.request_id, data=data, metadata=metadata)


@router.get("/health", response_model=ApiEnvelope)
def health(request: Request):
    return envelope(request, {"service": "trading-ai-production-api", "milestone": 40, "status": "UP"})


@router.get("/readiness", response_model=ApiEnvelope)
def readiness(request: Request, response: Response, _: str = Depends(require_access), svc: ProductionApiService = Depends(service)):
    ready, details = svc.readiness()
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return envelope(request, {"ready": ready, "components": details})


@router.get("/overview", response_model=ApiEnvelope)
def overview(request: Request, _: str = Depends(require_access), svc: ProductionApiService = Depends(service)):
    state = svc.platform_state()
    summary = {
        name: {
            "exists": doc.exists,
            "stale": doc.stale,
            "modified_at": doc.modified_at,
            "age_seconds": doc.age_seconds,
            "path": str(doc.path),
        }
        for name, doc in state.items()
    }
    return envelope(request, summary)


def artifact_response(request: Request, doc):
    if not doc.exists:
        raise HTTPException(status_code=404, detail=f"Artifact not found: {doc.path}")
    return envelope(request, doc.payload, artifact_path=str(doc.path), stale=doc.stale, age_seconds=doc.age_seconds)


@router.get("/portfolio", response_model=ApiEnvelope)
def portfolio(request: Request, _: str = Depends(require_access), svc: ProductionApiService = Depends(service)):
    return artifact_response(request, svc.artifact(svc.settings.portfolio_registry_file))


@router.get("/risk", response_model=ApiEnvelope)
def risk(request: Request, _: str = Depends(require_access), svc: ProductionApiService = Depends(service)):
    return artifact_response(request, svc.artifact(svc.settings.artifact_root / "m37/execution_risk_control.json"))


@router.get("/execution", response_model=ApiEnvelope)
def execution(request: Request, _: str = Depends(require_access), svc: ProductionApiService = Depends(service)):
    return artifact_response(request, svc.artifact(svc.settings.artifact_root / "m38/execution_queue.json"))


@router.get("/positions", response_model=ApiEnvelope)
def positions(request: Request, _: str = Depends(require_access), svc: ProductionApiService = Depends(service)):
    return artifact_response(request, svc.artifact(svc.settings.artifact_root / "m39/position_assessments.json"))


@router.get("/exit-instructions", response_model=ApiEnvelope)
def exits(request: Request, _: str = Depends(require_access), svc: ProductionApiService = Depends(service)):
    return artifact_response(request, svc.artifact(svc.settings.artifact_root / "m39/exit_instructions.json"))


@router.post("/workflows/{workflow}", response_model=ApiEnvelope)
def run_workflow(workflow: str, payload: WorkflowRunRequest, request: Request, actor: str = Depends(require_mutation_access), svc: ProductionApiService = Depends(service)):
    try:
        result = svc.run_workflow(workflow, payload.arguments)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown workflow") from exc
    if not result.accepted:
        raise HTTPException(status_code=409, detail=result.model_dump(mode="json"))
    return envelope(request, result.model_dump(mode="json"), actor=actor, requested_by=payload.requested_by, reason=payload.reason)

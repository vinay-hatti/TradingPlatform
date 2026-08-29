from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from trading_ai.production_api.security import require_access, require_mutation_access

from .service import OutcomeProbabilityService


router = APIRouter(prefix="/api/v1/outcome-probability", tags=["outcome-probability"])


def envelope(request: Request, data):
    return ApiEnvelope(request_id=request.state.request_id, data=data, metadata={})


def conflict(exc: Exception) -> HTTPException:
    return HTTPException(404 if isinstance(exc, KeyError) else 409, str(exc))


@router.get("/status", response_model=ApiEnvelope)
def status(request: Request, _: str = Depends(require_access)):
    with SessionLocal() as session:
        return envelope(request, OutcomeProbabilityService(session).status())


@router.post("/outcomes/materialize", response_model=ApiEnvelope)
def materialize(payload: dict, request: Request, actor: str = Depends(require_mutation_access)):
    with SessionLocal() as session:
        result = OutcomeProbabilityService(session).materialize_outcomes(
            max_candidates=payload.get("max_candidates")
        )
        return envelope(request, {"actor": actor, **result})


@router.post("/models/train", response_model=ApiEnvelope)
def train(payload: dict, request: Request, actor: str = Depends(require_mutation_access)):
    try:
        with SessionLocal() as session:
            result = OutcomeProbabilityService(session).train_challenger(
                model_version=payload.get("model_version")
            )
            return envelope(request, {"actor": actor, **result})
    except Exception as exc:
        raise conflict(exc)


@router.post("/models/{model_id}/approve-shadow", response_model=ApiEnvelope)
def approve(model_id: str, payload: dict, request: Request, actor: str = Depends(require_mutation_access)):
    try:
        with SessionLocal() as session:
            return envelope(
                request,
                OutcomeProbabilityService(session).approve_shadow_model(
                    model_id,
                    actor=actor,
                    reason=str(payload.get("reason") or ""),
                ),
            )
    except Exception as exc:
        raise conflict(exc)


@router.post("/models/{model_id}/activate-shadow", response_model=ApiEnvelope)
def activate(model_id: str, payload: dict, request: Request, actor: str = Depends(require_mutation_access)):
    try:
        with SessionLocal() as session:
            return envelope(
                request,
                OutcomeProbabilityService(session).activate_shadow_model(
                    model_id,
                    actor=actor,
                    reason=str(payload.get("reason") or ""),
                ),
            )
    except Exception as exc:
        raise conflict(exc)

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from trading_ai.production_api.security import require_access, require_mutation_access

from .profile import OpportunityCreate, OpportunityTransition, WorkflowState
from .service import OpportunityService

router = APIRouter(prefix="/api/v1/opportunities", tags=["opportunities"])

class StageOpportunityRequest(BaseModel):
    scanner_run_id: str
    snapshot_id: str
    snapshot_timestamp: str
    symbol: str
    direction: str
    strategy: str
    source_payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

class TransitionOpportunityRequest(BaseModel):
    new_state: WorkflowState
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)

def envelope(request: Request, data, **metadata) -> ApiEnvelope:
    return ApiEnvelope(request_id=request.state.request_id, data=data, metadata=metadata)

def _record(value):
    data=asdict(value)
    data["workflow_state"]=value.workflow_state.value
    return data

def _event(value):
    return {
        "event_id": value.event_id, "opportunity_id": value.opportunity_id,
        "opportunity_version": value.opportunity_version, "event_type": value.event_type,
        "previous_state": value.previous_state, "new_state": value.new_state,
        "actor": value.actor, "reason": value.reason, "event_timestamp": value.event_timestamp,
        "metadata": dict(value.metadata_json or {}),
    }

@router.get("", response_model=ApiEnvelope)
def list_opportunities(request: Request, state: str | None = None, limit: int = Query(100, ge=1, le=500), _: str = Depends(require_access)):
    with SessionLocal() as session:
        svc=OpportunityService(session)
        values=svc.repo.list(state=state, limit=limit)
        return envelope(request, [_record(svc._record(item)) for item in values], count=len(values))

@router.post("", response_model=ApiEnvelope, status_code=201)
def stage_opportunity(payload: StageOpportunityRequest, request: Request, actor: str = Depends(require_mutation_access)):
    with SessionLocal() as session:
        record=OpportunityService(session).create(OpportunityCreate(
            scanner_run_id=payload.scanner_run_id, snapshot_id=payload.snapshot_id,
            snapshot_timestamp=payload.snapshot_timestamp, symbol=payload.symbol,
            direction=payload.direction, strategy=payload.strategy,
            source_payload=payload.source_payload, created_by=actor, metadata=payload.metadata,
        ))
        return envelope(request, _record(record), actor=actor)

@router.get("/{opportunity_id}", response_model=ApiEnvelope)
def get_opportunity(opportunity_id: str, request: Request, _: str = Depends(require_access)):
    with SessionLocal() as session:
        svc=OpportunityService(session); model=svc.repo.get(opportunity_id)
        if model is None: raise HTTPException(404, "Opportunity not found")
        return envelope(request, _record(svc._record(model)))

@router.get("/{opportunity_id}/events", response_model=ApiEnvelope)
def get_events(opportunity_id: str, request: Request, _: str = Depends(require_access)):
    with SessionLocal() as session:
        svc=OpportunityService(session)
        if svc.repo.get(opportunity_id) is None: raise HTTPException(404, "Opportunity not found")
        values=svc.repo.events(opportunity_id)
        return envelope(request, [_event(item) for item in values], count=len(values))

@router.post("/{opportunity_id}/transitions", response_model=ApiEnvelope)
def transition_opportunity(opportunity_id: str, payload: TransitionOpportunityRequest, request: Request, actor: str = Depends(require_mutation_access)):
    with SessionLocal() as session:
        try:
            record=OpportunityService(session).transition(opportunity_id, OpportunityTransition(
                new_state=payload.new_state, actor=actor, reason=payload.reason,
                expected_version=payload.expected_version, metadata=payload.metadata,
            ))
        except KeyError as exc: raise HTTPException(404, str(exc)) from exc
        except RuntimeError as exc: raise HTTPException(409, str(exc)) from exc
        except ValueError as exc: raise HTTPException(422, str(exc)) from exc
        return envelope(request, _record(record), actor=actor)

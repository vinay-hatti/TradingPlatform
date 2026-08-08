from __future__ import annotations
from uuid import uuid4
from fastapi import APIRouter, Query
from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from .service import InstitutionalInflectionService

router = APIRouter(prefix="/api/v1/inflection-intelligence", tags=["Inflection Intelligence"])
service = InstitutionalInflectionService(SessionLocal)

@router.post("/build", response_model=ApiEnvelope)
def build(limit: int | None = Query(default=None, ge=1, le=5000), timeframe: str = "1d"):
    return ApiEnvelope(request_id=uuid4().hex, data=service.build(limit=limit, timeframe=timeframe))

@router.get("/current", response_model=ApiEnvelope)
def current(limit: int = Query(default=100, ge=1, le=5000)):
    result = service.current(limit=limit)
    return ApiEnvelope(request_id=uuid4().hex, data=result, metadata={"count": len(result["snapshots"])})

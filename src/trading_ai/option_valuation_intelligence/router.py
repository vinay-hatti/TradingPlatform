from uuid import uuid4
from fastapi import APIRouter, Query
from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from .service import InstitutionalOptionValuationService
router=APIRouter(prefix='/api/v1/option-valuation-intelligence',tags=['Option Valuation Intelligence'])
service=InstitutionalOptionValuationService(SessionLocal)
@router.post('/build',response_model=ApiEnvelope)
def build(limit:int|None=Query(None,ge=1,le=10000)): return ApiEnvelope(request_id=uuid4().hex,data=service.build(limit=limit))
@router.get('/current',response_model=ApiEnvelope)
def current(limit:int=Query(100,ge=1,le=5000)): return ApiEnvelope(request_id=uuid4().hex,data=service.current(limit))

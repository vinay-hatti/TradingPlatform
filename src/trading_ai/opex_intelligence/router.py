from uuid import uuid4
from fastapi import APIRouter, Query
from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from .service import OpexIntelligenceService
router=APIRouter(prefix='/api/v1/opex-intelligence',tags=['OPEX Intelligence'])
service=OpexIntelligenceService(SessionLocal)
@router.get('/dashboard',response_model=ApiEnvelope)
def dashboard(symbol:str|None=Query(default=None),history_limit:int=Query(default=8,ge=1,le=50)):
    data=service.dashboard(symbol=symbol,history_limit=history_limit);return ApiEnvelope(request_id=uuid4().hex,data=data,metadata={'count':len(data.get('forecasts',[]))})
@router.post('/refresh',response_model=ApiEnvelope)
def refresh(cycles:int=Query(default=3,ge=1,le=6)):
    data=service.refresh(cycles=cycles);return ApiEnvelope(request_id=uuid4().hex,data=data,metadata={})
@router.post('/realize-outcomes',response_model=ApiEnvelope)
def realize():
    data=service.realize_outcomes();return ApiEnvelope(request_id=uuid4().hex,data=data,metadata={})

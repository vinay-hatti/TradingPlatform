from uuid import uuid4
from fastapi import APIRouter
from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope
from .service import FuturesIntelligenceService
router=APIRouter(prefix='/api/v1/futures-intelligence',tags=['Futures Intelligence'])
service=FuturesIntelligenceService(SessionLocal)
@router.get('/latest',response_model=ApiEnvelope)
def latest():
    data=service.latest_map();return ApiEnvelope(request_id=uuid4().hex,data=data,metadata={'count':len(data)})

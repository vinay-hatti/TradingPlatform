from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Query

from trading_ai.database.session import SessionLocal
from trading_ai.production_api.models import ApiEnvelope

from .service import AnalyticsDashboardService

router = APIRouter(prefix='/api/v1/analytics-dashboard', tags=['Analytics Dashboard'])
service = AnalyticsDashboardService(SessionLocal)


@router.get('/inflection', response_model=ApiEnvelope)
def inflection(limit: int = Query(default=1000, ge=1, le=5000)):
    result = service.inflection(limit=limit)
    return ApiEnvelope(request_id=uuid4().hex, data=result, metadata={'count': len(result.get('candidates', []))})


@router.get('/options-mispricing', response_model=ApiEnvelope)
def options_mispricing(limit: int = Query(default=3000, ge=1, le=10000)):
    result = service.mispricing(limit=limit)
    return ApiEnvelope(request_id=uuid4().hex, data=result, metadata={'count': len(result.get('candidates', []))})

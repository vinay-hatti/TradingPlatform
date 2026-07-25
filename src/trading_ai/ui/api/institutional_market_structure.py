from __future__ import annotations
from datetime import date
from fastapi import APIRouter, HTTPException, Query
from trading_ai.institutional_market_structure.service import InstitutionalMarketStructureService

router=APIRouter(prefix="/api/v1/institutional-market-structure",tags=["institutional-market-structure"])

@router.get("/{symbol}")
def get_market_structure(symbol: str, as_of: date = Query(default_factory=date.today)):
    try:
        snapshot=InstitutionalMarketStructureService().run(symbol,as_of,persist=True)
        return snapshot.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404,detail=str(exc)) from exc

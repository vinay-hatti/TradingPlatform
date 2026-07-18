from fastapi import APIRouter, Depends, Path, Query
from trading_ai.ui.models.symbol_intelligence import SymbolIntelligenceResponse
from trading_ai.ui.services.symbol_intelligence_service import SymbolIntelligenceService
router = APIRouter(prefix="/api/v1/symbols", tags=["symbols"])
def service(): return SymbolIntelligenceService()
@router.get("/{symbol}", response_model=SymbolIntelligenceResponse)
def symbol_intelligence(
    symbol: str = Path(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.\-]+$"),
    days: int = Query(default=252, ge=20, le=1000),
    intelligence: SymbolIntelligenceService = Depends(service),
):
    return intelligence.get(symbol, days)

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from trading_ai.ui.models.option_chain import OptionChainQuery
from trading_ai.ui.services.option_chain_service import InstitutionalOptionChainService

router = APIRouter(prefix="/api/v1/option-chain", tags=["option-chain"])


def service() -> InstitutionalOptionChainService:
    return InstitutionalOptionChainService()


@router.get("/expirations/{symbol}")
def expirations(
    symbol: str,
    quote_date: date | None = Query(default=None),
    chain_service: InstitutionalOptionChainService = Depends(service),
):
    try:
        return {
            "symbol": symbol.upper(),
            "quote_date": quote_date,
            "expirations": chain_service.expirations(symbol, quote_date),
        }
    except Exception as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.get("/{symbol}")
def option_chain(
    symbol: str,
    expiration: date | None = Query(default=None),
    quote_date: date | None = Query(default=None),
    min_strike: float | None = Query(default=None, gt=0),
    max_strike: float | None = Query(default=None, gt=0),
    option_type: Literal["CALL", "PUT", "ALL"] = Query(default="ALL"),
    min_volume: int = Query(default=0, ge=0),
    min_open_interest: int = Query(default=0, ge=0),
    max_spread_pct: float = Query(default=1.0, ge=0),
    risk_free_rate: float = Query(default=0.04),
    limit: int = Query(default=500, ge=1, le=5000),
    chain_service: InstitutionalOptionChainService = Depends(service),
):
    try:
        return chain_service.snapshot(
            OptionChainQuery(
                symbol=symbol,
                expiration=expiration,
                quote_date=quote_date,
                min_strike=min_strike,
                max_strike=max_strike,
                option_type=option_type,
                min_volume=min_volume,
                min_open_interest=min_open_interest,
                max_spread_pct=max_spread_pct,
                risk_free_rate=risk_free_rate,
                limit=limit,
            )
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=422, detail=str(error))

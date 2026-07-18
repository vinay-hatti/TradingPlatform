from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from trading_ai.ui.models.opportunity import OpportunityScreenerResponse
from trading_ai.ui.services.opportunity_screener_service import (
    OpportunityScreenerService,
)

router = APIRouter(prefix="/api/v1", tags=["opportunities"])


def service() -> OpportunityScreenerService:
    return OpportunityScreenerService()


@router.get("/opportunities", response_model=OpportunityScreenerResponse)
def opportunities(
    search: str | None = None,
    symbol: str | None = None,
    direction: str | None = None,
    regime: str | None = None,
    strategy: str | None = None,
    status: str | None = None,
    min_score: float | None = Query(default=None, ge=0, le=100),
    min_pop: float | None = Query(default=None, ge=0, le=100),
    max_spread_pct: float | None = Query(default=None, ge=0),
    min_volume: int | None = Query(default=None, ge=0),
    min_open_interest: int | None = Query(default=None, ge=0),
    sort_by: str = "score",
    sort_order: str = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    screener: OpportunityScreenerService = Depends(service),
) -> OpportunityScreenerResponse:
    return screener.query(
        search=search,
        symbol=symbol,
        direction_filter=direction,
        regime=regime,
        strategy=strategy,
        status=status,
        min_score=min_score,
        min_pop=min_pop,
        max_spread_pct=max_spread_pct,
        min_volume=min_volume,
        min_open_interest=min_open_interest,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.get("/opportunities/export.csv")
def export_opportunities(
    search: str | None = None,
    symbol: str | None = None,
    direction: str | None = None,
    min_score: float | None = None,
    min_pop: float | None = None,
    screener: OpportunityScreenerService = Depends(service),
) -> StreamingResponse:
    response = screener.query(
        search=search,
        symbol=symbol,
        direction_filter=direction,
        min_score=min_score,
        min_pop=min_pop,
        page=1,
        page_size=200,
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "rank", "symbol", "direction", "strategy", "score",
        "probability_of_profit", "expected_value", "regime", "status",
        "contract", "expiry", "strike", "bid", "ask", "spread_pct",
        "volume", "open_interest", "implied_volatility", "delta",
        "gamma", "theta", "vega", "liquidity_score", "source", "as_of",
    ])
    for item in response.records:
        writer.writerow([
            item.rank, item.symbol, item.direction, item.strategy, item.score,
            item.probability_of_profit, item.expected_value, item.regime,
            item.status, item.contract, item.expiry, item.strike, item.bid,
            item.ask, item.spread_pct, item.volume, item.open_interest,
            item.implied_volatility, item.delta, item.gamma, item.theta,
            item.vega, item.liquidity_score, item.source, item.as_of.isoformat(),
        ])

    payload = buffer.getvalue().encode("utf-8")
    return StreamingResponse(
        iter([payload]),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                "attachment; filename=trading_ai_opportunities.csv"
            )
        },
    )

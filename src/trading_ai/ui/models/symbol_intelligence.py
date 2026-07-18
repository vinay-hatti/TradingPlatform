from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, Field

class PricePoint(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int

class TechnicalSnapshot(BaseModel):
    close: float | None = None
    change_1d_pct: float | None = None
    change_5d_pct: float | None = None
    change_20d_pct: float | None = None
    high_52w: float | None = None
    low_52w: float | None = None
    distance_from_high_pct: float | None = None
    average_volume_20d: float | None = None
    realized_volatility_20d: float | None = None
    sma20: float | None = None
    sma50: float | None = None
    sma200: float | None = None
    rsi14: float | None = None
    atr14: float | None = None
    trend: str = "UNKNOWN"
    regime: str = "UNKNOWN"

class SymbolOpportunity(BaseModel):
    signal: str = "WATCH"
    strategy: str = "Unknown"
    score: float | None = None
    ai_score: float | None = None
    probability_of_profit: float | None = None
    contract: str | None = None
    strike: float | None = None
    expiry: str | None = None
    bid: float | None = None
    ask: float | None = None
    spread_pct: float | None = None
    open_interest: int | None = None
    option_volume: int | None = None
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    liquidity_score: float | None = None
    ranking_reason: str | None = None
    source: str
    as_of: datetime

class SymbolIntelligenceResponse(BaseModel):
    generated_at: datetime
    symbol: str
    price_source: str
    price_as_of: datetime | None = None
    stale: bool
    age_seconds: float | None = None
    technicals: TechnicalSnapshot
    latest_opportunity: SymbolOpportunity | None = None
    opportunity_history: list[SymbolOpportunity] = Field(default_factory=list)
    price_history: list[PricePoint] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)

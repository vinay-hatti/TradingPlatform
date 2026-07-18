from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class OpportunityFilterOptions(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    directions: list[str] = Field(default_factory=list)
    regimes: list[str] = Field(default_factory=list)
    strategies: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class OpportunityRecord(BaseModel):
    rank: int = Field(ge=1)
    symbol: str
    direction: Literal["CALL", "PUT", "WATCH"]
    strategy: str
    score: float = Field(ge=0, le=100)
    probability_of_profit: float | None = Field(default=None, ge=0, le=1)
    expected_value: float | None = None
    regime: str
    status: str
    contract: str | None = None
    expiry: str | None = None
    strike: float | None = None
    option_type: str | None = None
    bid: float | None = None
    ask: float | None = None
    spread_pct: float | None = None
    volume: int | None = None
    open_interest: int | None = None
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    liquidity_score: float | None = None
    confidence_grade: str | None = None
    source: str
    as_of: datetime
    notes: list[str] = Field(default_factory=list)


class OpportunityScreenerResponse(BaseModel):
    generated_at: datetime
    total_records: int
    filtered_records: int
    page: int
    page_size: int
    total_pages: int
    sort_by: str
    sort_order: Literal["asc", "desc"]
    records: list[OpportunityRecord]
    filters: OpportunityFilterOptions
    source_detail: str
    stale: bool
    age_seconds: float

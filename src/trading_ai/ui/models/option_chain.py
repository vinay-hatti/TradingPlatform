from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class OptionChainQuery(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    expiration: date | None = None
    quote_date: date | None = None
    min_strike: float | None = Field(default=None, gt=0)
    max_strike: float | None = Field(default=None, gt=0)
    option_type: Literal["CALL", "PUT", "ALL"] = "ALL"
    min_volume: int = Field(default=0, ge=0)
    min_open_interest: int = Field(default=0, ge=0)
    max_spread_pct: float = Field(default=1.0, ge=0)
    risk_free_rate: float = Field(default=0.04, ge=-0.10, le=0.50)
    limit: int = Field(default=500, ge=1, le=5000)


class OptionChainContract(BaseModel):
    contract_key: str
    underlying_symbol: str
    quote_date: date
    expiration: date
    days_to_expiration: int
    option_type: Literal["CALL", "PUT"]
    strike: float
    bid: float
    ask: float
    last: float
    mid: float
    spread: float
    spread_pct: float
    volume: int
    open_interest: int
    implied_volatility: float
    delta: float
    gamma: float
    theta: float
    vega: float
    intrinsic_value: float
    extrinsic_value: float
    moneyness_pct: float
    liquidity_score: float
    quote_quality: Literal["GOOD", "FAIR", "POOR"]
    greek_source: Literal["PROVIDER", "CALCULATED", "MIXED"]


class VolatilitySmilePoint(BaseModel):
    strike: float
    call_iv: float | None = None
    put_iv: float | None = None
    call_volume: int = 0
    put_volume: int = 0
    call_open_interest: int = 0
    put_open_interest: int = 0


class LiquidityLadderRow(BaseModel):
    strike: float
    call_bid: float | None = None
    call_ask: float | None = None
    call_volume: int = 0
    call_open_interest: int = 0
    put_bid: float | None = None
    put_ask: float | None = None
    put_volume: int = 0
    put_open_interest: int = 0


class OptionChainSnapshot(BaseModel):
    symbol: str
    quote_date: date
    expiration: date
    underlying_price: float
    generated_at: datetime
    expirations: list[date]
    contracts: list[OptionChainContract]
    volatility_smile: list[VolatilitySmilePoint]
    liquidity_ladder: list[LiquidityLadderRow]
    put_call_volume_ratio: float | None
    put_call_open_interest_ratio: float | None
    total_call_volume: int
    total_put_volume: int
    total_call_open_interest: int
    total_put_open_interest: int
    data_source: str
    delayed: bool = True

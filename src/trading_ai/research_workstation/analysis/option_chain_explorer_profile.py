from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class OptionContractAnalysisProfile:
    symbol: str
    expiration: date | None
    days_to_expiration: int
    strike: float
    option_type: str
    bid: float
    ask: float
    mark: float
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
    contract_score: float
    liquidity_grade: str
    moneyness: str
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExpirationAnalysisProfile:
    expiration: date | None
    days_to_expiration: int
    contract_count: int
    call_count: int
    put_count: int
    total_volume: int
    total_open_interest: int
    average_spread_pct: float
    median_implied_volatility: float
    call_put_volume_ratio: float
    call_put_open_interest_ratio: float
    liquidity_score: float
    expiration_score: float
    quality_grade: str
    preferred: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class OptionChainExplorerProfile:
    symbol: str
    underlying_price: float
    quote_date: date | None
    contract_count: int
    expiration_count: int
    preferred_expiration: date | None
    expirations: tuple[ExpirationAnalysisProfile, ...]
    contracts: tuple[OptionContractAnalysisProfile, ...]
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

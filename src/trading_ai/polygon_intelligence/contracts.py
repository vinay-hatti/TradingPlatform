from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Any

@dataclass(frozen=True)
class OptionSnapshotRun:
    snapshot_id: str
    snapshot_timestamp: datetime
    as_of_date: date
    provider: str = "POLYGON"
    status: str = "BUILDING"
    is_partial: bool = False
    completeness_score: float = 0.0
    warnings: tuple[str, ...] = ()

@dataclass(frozen=True)
class OptionContractSnapshot:
    snapshot_id: str
    snapshot_timestamp: datetime
    underlying_symbol: str
    option_symbol: str
    expiry: date
    option_type: str
    strike: float
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    volume: int | None = None
    open_interest: int | None = None
    implied_volatility: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    vanna: float | None = None
    charm: float | None = None
    underlying_price: float | None = None
    quote_timestamp: datetime | None = None
    trade_timestamp: datetime | None = None
    quote_quality: str = "UNKNOWN"

@dataclass(frozen=True)
class InstitutionalMarketContext:
    snapshot_timestamp: datetime | None = None
    market_bias: str = "NEUTRAL"
    market_health_score: float = 50.0
    market_sentiment_score: float = 50.0
    market_risk_score: float = 50.0
    trend_regime: str = "UNKNOWN"
    volatility_regime: str = "UNKNOWN"
    correlation_regime: str = "UNKNOWN"
    liquidity_regime: str = "UNKNOWN"
    transition_risk: float = 50.0
    sector: str = "UNKNOWN"
    sector_breadth_score: float = 50.0
    sector_rotation_label: str = "UNKNOWN"
    sector_relative_strength: float = 50.0
    dealer_positioning_score: float = 50.0
    dealer_conviction_score: float = 0.0
    dealer_alignment: str = "NEUTRAL"
    strategy_fit: str = "NEUTRAL"
    opportunity_alignment: float = 50.0
    confidence: float = 0.0
    freshness_status: str = "UNAVAILABLE"
    warnings: tuple[str, ...] = ()
    provenance: str = "UNAVAILABLE"

@dataclass(frozen=True)
class MarketContextEvaluation:
    outcome: str
    allowed: bool
    total_adjustment: float
    market_alignment_adjustment: float = 0.0
    sector_alignment_adjustment: float = 0.0
    volatility_suitability_adjustment: float = 0.0
    dealer_alignment_adjustment: float = 0.0
    liquidity_adjustment: float = 0.0
    risk_adjustment: float = 0.0
    data_confidence_adjustment: float = 0.0
    reasons: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    confidence: float = 0.0
    context: InstitutionalMarketContext = field(default_factory=InstitutionalMarketContext)
    def to_dict(self) -> dict[str, Any]: return asdict(self)

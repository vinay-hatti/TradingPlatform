from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class MarketOverviewSnapshot:
    snapshot_timestamp: datetime
    as_of_date: str
    market_bias: str
    preferred_strategy: str
    market_health_score: float
    trend_score: float
    momentum_score: float
    breadth_score: float
    risk_on_score: float
    sentiment_score: float
    confidence_score: float
    trend_regime: str
    volatility_regime: str
    breadth_regime: str
    liquidity_regime: str
    correlation_regime: str
    regime_transition_risk: str
    index_context: list[dict[str, Any]] = field(default_factory=list)
    breadth: dict[str, Any] = field(default_factory=dict)
    trend_momentum: dict[str, Any] = field(default_factory=dict)
    regime_sentiment: dict[str, Any] = field(default_factory=dict)
    sectors: list[dict[str, Any]] = field(default_factory=list)
    dealer_positioning: list[dict[str, Any]] = field(default_factory=list)
    volatility_options: dict[str, Any] = field(default_factory=dict)
    liquidity_participation: dict[str, Any] = field(default_factory=dict)
    cross_asset: list[dict[str, Any]] = field(default_factory=list)
    risk_alerts: list[dict[str, Any]] = field(default_factory=list)
    opportunity_map: dict[str, Any] = field(default_factory=dict)
    data_freshness: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    trend_intelligence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["snapshot_timestamp"] = self.snapshot_timestamp.isoformat()
        return payload

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ScannerFilterProfile:
    min_price: float | None = None
    max_price: float | None = None
    min_average_volume: int | None = None
    min_option_volume: int | None = None
    min_open_interest: int | None = None
    max_spread_pct: float | None = None
    min_iv_rank: float | None = None
    min_iv_percentile: float | None = None
    minimum_atr_pct: float | None = None
    required_regimes: tuple[str, ...] = ()
    required_signals: tuple[str, ...] = ()
    excluded_symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class MarketScanRequestProfile:
    scan_id: str
    universe: tuple[str, ...]
    filters: ScannerFilterProfile = field(default_factory=ScannerFilterProfile)
    maximum_results: int = 50
    minimum_composite_score: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class MarketCandidateProfile:
    symbol: str
    price: float
    average_volume: int
    option_volume: int
    open_interest: int
    spread_pct: float
    iv_rank: float
    iv_percentile: float
    atr_pct: float
    trend_score: float
    momentum_score: float
    liquidity_score: float
    volatility_score: float
    regime_score: float
    decision_confidence: float
    expected_return: float
    risk_score: float
    reward_risk_ratio: float
    signal: str
    regime: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RankedMarketCandidateProfile:
    rank: int
    symbol: str
    composite_score: float
    edge_score: float
    probability_score: float
    expected_return: float
    risk_score: float
    reward_risk_ratio: float
    signal: str
    regime: str
    source: MarketCandidateProfile

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source"] = asdict(self.source)
        return payload


@dataclass(frozen=True)
class MarketScanResultProfile:
    scan_id: str
    universe_size: int
    evaluated_count: int
    rejected_count: int
    ranked_candidates: tuple[RankedMarketCandidateProfile, ...]
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "universe_size": self.universe_size,
            "evaluated_count": self.evaluated_count,
            "rejected_count": self.rejected_count,
            "ranked_candidates": [
                candidate.to_dict() for candidate in self.ranked_candidates
            ],
            "completed_at": self.completed_at.isoformat(),
        }

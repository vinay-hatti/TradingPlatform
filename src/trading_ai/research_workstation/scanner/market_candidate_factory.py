from __future__ import annotations

from dataclasses import dataclass

from .market_feature_adapter import MarketFeatureSnapshot
from .market_scanner_profile import MarketCandidateProfile


@dataclass(frozen=True)
class CandidateEnrichmentDefaults:
    option_volume: int = 0
    open_interest: int = 0
    spread_pct: float = 1.0
    iv_rank: float = 0.0
    iv_percentile: float = 0.0
    decision_confidence: float = 50.0
    expected_return: float = 0.0
    risk_score: float = 50.0
    reward_risk_ratio: float = 0.0


class MarketCandidateFactory:
    def __init__(self, defaults: CandidateEnrichmentDefaults | None = None):
        self.defaults = defaults or CandidateEnrichmentDefaults()

    def from_feature_snapshot(
        self,
        snapshot: MarketFeatureSnapshot,
    ) -> MarketCandidateProfile:
        return MarketCandidateProfile(
            symbol=snapshot.symbol,
            price=snapshot.price,
            average_volume=snapshot.average_volume,
            option_volume=self.defaults.option_volume,
            open_interest=self.defaults.open_interest,
            spread_pct=self.defaults.spread_pct,
            iv_rank=self.defaults.iv_rank,
            iv_percentile=self.defaults.iv_percentile,
            atr_pct=snapshot.atr_pct,
            trend_score=snapshot.trend_score,
            momentum_score=snapshot.momentum_score,
            liquidity_score=snapshot.liquidity_score,
            volatility_score=snapshot.volatility_score,
            regime_score=snapshot.regime_score,
            decision_confidence=self.defaults.decision_confidence,
            expected_return=self.defaults.expected_return,
            risk_score=self.defaults.risk_score,
            reward_risk_ratio=self.defaults.reward_risk_ratio,
            signal=snapshot.signal,
            regime=snapshot.regime,
            metadata=dict(snapshot.metadata),
        )

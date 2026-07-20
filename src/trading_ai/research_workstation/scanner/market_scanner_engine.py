from __future__ import annotations

from .market_scanner_policy import MarketScannerPolicy
from .market_scanner_profile import (
    MarketCandidateProfile,
    MarketScanRequestProfile,
    MarketScanResultProfile,
    RankedMarketCandidateProfile,
)


class MarketScannerEngine:
    def __init__(self, policy: MarketScannerPolicy | None = None):
        self.policy = policy or MarketScannerPolicy()
        self.policy.validate()

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
        return max(low, min(high, float(value)))

    def composite_score(self, candidate: MarketCandidateProfile) -> float:
        expected_return_score = self._clamp(candidate.expected_return * 100.0)
        reward_risk_score = self._clamp(candidate.reward_risk_ratio * 20.0)

        score = (
            self._clamp(candidate.trend_score) * self.policy.trend_weight
            + self._clamp(candidate.momentum_score) * self.policy.momentum_weight
            + self._clamp(candidate.liquidity_score) * self.policy.liquidity_weight
            + self._clamp(candidate.volatility_score) * self.policy.volatility_weight
            + self._clamp(candidate.regime_score) * self.policy.regime_weight
            + self._clamp(candidate.decision_confidence)
            * self.policy.probability_weight
            + expected_return_score * self.policy.expected_return_weight
            + reward_risk_score * self.policy.reward_risk_weight
        )
        return round(score, 6)

    def edge_score(self, candidate: MarketCandidateProfile) -> float:
        risk_penalty = self._clamp(candidate.risk_score) / 100.0
        raw_edge = (
            candidate.decision_confidence
            * max(candidate.expected_return, 0.0)
            * max(candidate.reward_risk_ratio, 0.0)
            * (1.0 - risk_penalty)
        )
        return round(raw_edge, 6)

    def scan(
        self,
        request: MarketScanRequestProfile,
        candidates: list[MarketCandidateProfile],
    ) -> MarketScanResultProfile:
        accepted: list[tuple[MarketCandidateProfile, float, float]] = []
        rejected_count = 0

        for candidate in candidates:
            accepted_by_policy, _ = self.policy.accepts(candidate, request)
            if not accepted_by_policy:
                rejected_count += 1
                continue

            composite = self.composite_score(candidate)
            if composite < request.minimum_composite_score:
                rejected_count += 1
                continue

            accepted.append((candidate, composite, self.edge_score(candidate)))

        accepted.sort(
            key=lambda item: (
                item[1],
                item[2],
                item[0].decision_confidence,
                item[0].expected_return,
            ),
            reverse=True,
        )

        ranked = tuple(
            RankedMarketCandidateProfile(
                rank=index,
                symbol=candidate.symbol,
                composite_score=composite,
                edge_score=edge,
                probability_score=round(candidate.decision_confidence, 6),
                expected_return=round(candidate.expected_return, 6),
                risk_score=round(candidate.risk_score, 6),
                reward_risk_ratio=round(candidate.reward_risk_ratio, 6),
                signal=candidate.signal,
                regime=candidate.regime,
                source=candidate,
            )
            for index, (candidate, composite, edge) in enumerate(
                accepted[: request.maximum_results],
                start=1,
            )
        )

        return MarketScanResultProfile(
            scan_id=request.scan_id,
            universe_size=len(request.universe),
            evaluated_count=len(candidates),
            rejected_count=rejected_count,
            ranked_candidates=ranked,
        )

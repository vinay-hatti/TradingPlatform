from __future__ import annotations

from typing import Any, Mapping

from trading_ai.research_workstation.scanner.market_scanner_profile import (
    MarketCandidateProfile,
)

from .candidate_analysis_policy import CandidateAnalysisPolicy
from .candidate_analysis_profile import (
    CandidateAnalysisProfile,
    DecisionExplanationProfile,
    InstitutionalAnalysisProfile,
    LiquidityAnalysisProfile,
    RiskAnalysisProfile,
    TechnicalAnalysisProfile,
    VolatilityAnalysisProfile,
)


class CandidateAnalysisEngine:
    def __init__(
        self,
        policy: CandidateAnalysisPolicy | None = None,
    ):
        self.policy = policy or CandidateAnalysisPolicy()
        self.policy.validate()

    @staticmethod
    def _bound(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    def _technical(
        self,
        candidate: MarketCandidateProfile,
    ) -> TechnicalAnalysisProfile:
        technical_score = round(
            (
                float(candidate.trend_score)
                + float(candidate.momentum_score)
                + float(candidate.regime_score)
            )
            / 3.0,
            6,
        )
        positives: list[str] = []
        negatives: list[str] = []

        if candidate.trend_score >= 70:
            positives.append("Strong trend alignment")
        elif candidate.trend_score < 45:
            negatives.append("Weak trend structure")

        if candidate.momentum_score >= 70:
            positives.append("Strong momentum confirmation")
        elif candidate.momentum_score < 45:
            negatives.append("Weak momentum confirmation")

        if candidate.regime_score >= 70:
            positives.append("Supportive market regime")
        elif candidate.regime_score < 45:
            negatives.append("Unfavorable market regime")

        return TechnicalAnalysisProfile(
            trend_score=float(candidate.trend_score),
            momentum_score=float(candidate.momentum_score),
            regime_score=float(candidate.regime_score),
            technical_score=technical_score,
            signal=str(candidate.signal),
            regime=str(candidate.regime),
            positive_factors=tuple(positives),
            negative_factors=tuple(negatives),
        )

    def _liquidity(
        self,
        candidate: MarketCandidateProfile,
    ) -> LiquidityAnalysisProfile:
        policy = self.policy
        positives: list[str] = []
        negatives: list[str] = []

        if candidate.average_volume >= policy.strong_volume_threshold:
            positives.append("High underlying trading volume")
        else:
            negatives.append("Underlying volume below institutional preference")

        if candidate.option_volume >= policy.strong_option_volume_threshold:
            positives.append("Strong option volume")
        else:
            negatives.append("Limited option volume")

        if candidate.open_interest >= policy.strong_open_interest_threshold:
            positives.append("Strong option open interest")
        else:
            negatives.append("Limited option open interest")

        if candidate.spread_pct <= policy.maximum_healthy_spread_pct:
            positives.append("Efficient bid/ask spread")
        else:
            negatives.append("Wide bid/ask spread")

        score = self._bound(float(candidate.liquidity_score))
        quality = (
            "INSTITUTIONAL"
            if score >= 80
            else "ACCEPTABLE"
            if score >= 60
            else "WEAK"
        )

        return LiquidityAnalysisProfile(
            average_volume=int(candidate.average_volume),
            option_volume=int(candidate.option_volume),
            open_interest=int(candidate.open_interest),
            spread_pct=float(candidate.spread_pct),
            liquidity_score=score,
            market_quality=quality,
            positive_factors=tuple(positives),
            negative_factors=tuple(negatives),
        )

    def _volatility(
        self,
        candidate: MarketCandidateProfile,
    ) -> VolatilityAnalysisProfile:
        positives: list[str] = []
        negatives: list[str] = []

        if candidate.iv_rank >= self.policy.strong_iv_rank_threshold:
            positives.append("Elevated IV rank supports premium opportunity")
        else:
            negatives.append("IV rank offers limited premium edge")

        if candidate.iv_percentile >= 50:
            positives.append("Implied volatility is elevated historically")

        if candidate.atr_pct > self.policy.elevated_atr_pct:
            negatives.append("Elevated realized movement increases risk")
            state = "ELEVATED"
        elif candidate.atr_pct >= 1.0:
            positives.append("Tradable realized volatility")
            state = "NORMAL"
        else:
            negatives.append("Low realized movement may limit opportunity")
            state = "COMPRESSED"

        return VolatilityAnalysisProfile(
            iv_rank=float(candidate.iv_rank),
            iv_percentile=float(candidate.iv_percentile),
            atr_pct=float(candidate.atr_pct),
            volatility_score=self._bound(candidate.volatility_score),
            volatility_state=state,
            positive_factors=tuple(positives),
            negative_factors=tuple(negatives),
        )

    def _institutional(
        self,
        candidate: MarketCandidateProfile,
    ) -> InstitutionalAnalysisProfile:
        metadata = self._mapping(candidate.metadata)
        institutional = self._mapping(
            metadata.get("institutional_decision", {})
        )

        available = bool(institutional.get("available", institutional))
        probability = self._number(
            institutional.get("probability_of_profit", 0.0)
        )
        calibrated = self._number(
            institutional.get("calibrated_probability", probability)
        )
        score = self._number(
            institutional.get(
                "institutional_score",
                candidate.decision_confidence,
            )
        )

        positives: list[str] = []
        negatives: list[str] = []

        if available:
            positives.append("Institutional decision analytics available")
        else:
            negatives.append("Institutional decision analytics unavailable")

        if calibrated >= 0.70:
            positives.append("Strong calibrated probability of profit")
        elif available:
            negatives.append("Calibrated probability below preferred level")

        if institutional.get("allowed", False):
            positives.append("Institutional policy permits the trade")
        elif available:
            negatives.append("Institutional policy does not permit the trade")

        if institutional.get("selected", False):
            positives.append("Selected by institutional ranking")
        elif available:
            negatives.append("Not selected by institutional ranking")

        tail_grade = str(
            institutional.get("tail_risk_grade", "UNKNOWN")
        )
        if tail_grade in {"A", "B"}:
            positives.append("Favorable tail-risk grade")
        elif tail_grade not in {"UNKNOWN", ""}:
            negatives.append("Elevated tail-risk grade")

        return InstitutionalAnalysisProfile(
            available=available,
            strategy=str(
                institutional.get("strategy", "UNAVAILABLE")
            ),
            action=str(institutional.get("action", "HOLD")),
            readiness=str(
                institutional.get("readiness", "UNKNOWN")
            ),
            allowed=bool(institutional.get("allowed", False)),
            selected=bool(institutional.get("selected", False)),
            probability_of_profit=probability,
            calibrated_probability=calibrated,
            institutional_score=self._bound(score),
            decision_confidence=self._bound(
                candidate.decision_confidence
            ),
            tail_risk_grade=tail_grade,
            recommended_position_size_pct=self._number(
                institutional.get(
                    "recommended_position_size_pct",
                    0.0,
                )
            ),
            positive_factors=tuple(positives),
            negative_factors=tuple(negatives),
        )

    def _risk(
        self,
        candidate: MarketCandidateProfile,
    ) -> RiskAnalysisProfile:
        institutional = self._mapping(
            self._mapping(candidate.metadata).get(
                "institutional_decision",
                {},
            )
        )
        positives: list[str] = []
        negatives: list[str] = []

        if candidate.reward_risk_ratio >= (
            self.policy.minimum_reward_risk_ratio
        ):
            positives.append("Reward/risk ratio meets policy")
        else:
            negatives.append("Reward/risk ratio below policy")

        if candidate.expected_return > 0:
            positives.append("Positive modeled expected return")
        else:
            negatives.append("Non-positive modeled expected return")

        if candidate.risk_score >= self.policy.high_risk_score:
            negatives.append("Elevated aggregate risk score")
            grade = "HIGH"
        elif candidate.risk_score >= 45:
            grade = "MODERATE"
        else:
            positives.append("Controlled aggregate risk score")
            grade = "LOW"

        return RiskAnalysisProfile(
            risk_score=self._bound(candidate.risk_score),
            expected_return=float(candidate.expected_return),
            reward_risk_ratio=float(candidate.reward_risk_ratio),
            stop_loss_pct=self._number(
                institutional.get("stop_loss_pct", 0.0)
            ),
            take_profit_pct=self._number(
                institutional.get("take_profit_pct", 0.0)
            ),
            risk_grade=grade,
            positive_factors=tuple(positives),
            negative_factors=tuple(negatives),
        )

    def analyze(
        self,
        candidate: MarketCandidateProfile,
        *,
        composite_score: float | None = None,
    ) -> CandidateAnalysisProfile:
        technical = self._technical(candidate)
        liquidity = self._liquidity(candidate)
        volatility = self._volatility(candidate)
        institutional = self._institutional(candidate)
        risk = self._risk(candidate)

        reward_risk_quality = self._bound(
            candidate.reward_risk_ratio * 25.0
        )
        readiness_score = round(
            technical.technical_score * self.policy.technical_weight
            + liquidity.liquidity_score * self.policy.liquidity_weight
            + volatility.volatility_score
            * self.policy.volatility_weight
            + institutional.institutional_score
            * self.policy.institutional_weight
            + reward_risk_quality
            * self.policy.risk_reward_weight,
            6,
        )

        if readiness_score >= self.policy.ready_threshold:
            readiness = "READY"
        elif readiness_score >= self.policy.watch_threshold:
            readiness = "WATCH"
        else:
            readiness = "NOT_READY"

        positives = (
            technical.positive_factors
            + liquidity.positive_factors
            + volatility.positive_factors
            + institutional.positive_factors
            + risk.positive_factors
        )
        negatives = (
            technical.negative_factors
            + liquidity.negative_factors
            + volatility.negative_factors
            + institutional.negative_factors
            + risk.negative_factors
        )

        warnings = tuple(
            factor
            for factor in negatives
            if (
                "Wide" in factor
                or "Elevated" in factor
                or "unavailable" in factor
            )
        )

        strategy = (
            institutional.strategy
            if institutional.strategy != "UNAVAILABLE"
            else candidate.signal
        )
        summary = (
            f"{candidate.symbol} is {readiness.lower().replace('_', ' ')} "
            f"with a trade-readiness score of {readiness_score:.2f}. "
            f"The preferred direction or strategy is {strategy}."
        )

        explanation = DecisionExplanationProfile(
            recommendation=strategy,
            readiness=readiness,
            confidence=self._bound(candidate.decision_confidence),
            summary=summary,
            positive_contributors=positives,
            negative_contributors=negatives,
            warnings=warnings,
            rejection_factors=tuple(
                self._mapping(candidate.metadata)
                .get("institutional_decision", {})
                .get("rejection_reasons", ())
            ),
        )

        return CandidateAnalysisProfile(
            symbol=candidate.symbol,
            price=float(candidate.price),
            signal=candidate.signal,
            regime=candidate.regime,
            composite_score=float(
                candidate.decision_confidence
                if composite_score is None
                else composite_score
            ),
            trade_readiness_score=readiness_score,
            technical=technical,
            liquidity=liquidity,
            volatility=volatility,
            institutional=institutional,
            risk=risk,
            explanation=explanation,
            warnings=warnings,
            metadata={
                "source": "M34_PHASE2_CANDIDATE_ANALYSIS",
                "policy_version": "1.0",
            },
        )

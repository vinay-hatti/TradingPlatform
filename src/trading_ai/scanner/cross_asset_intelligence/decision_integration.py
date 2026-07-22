from __future__ import annotations

from .contracts import CrossAssetDecisionAdjustment
from .policy import CrossAssetIntelligencePolicy


class CrossAssetDecisionIntegrationEngine:
    def __init__(
        self,
        policy: CrossAssetIntelligencePolicy | None = None,
    ) -> None:
        self.policy = policy or CrossAssetIntelligencePolicy()

    def build_adjustment(
        self,
        *,
        tactical_bias: str,
        systemic_risk_level: str,
        opportunity_regime: str,
        composite_confidence: float,
        governance_status: str,
    ) -> CrossAssetDecisionAdjustment:
        rationale: list[str] = []

        if tactical_bias == "BULLISH":
            call_adjustment = min(
                self.policy.maximum_call_adjustment,
                0.05 + 0.15 * composite_confidence,
            )
            put_adjustment = -min(
                self.policy.maximum_put_adjustment,
                0.03 + 0.10 * composite_confidence,
            )
            preferred_direction = "CALL"
            rationale.append("cross-asset intelligence favors bullish exposure")
        elif tactical_bias == "BEARISH":
            call_adjustment = -min(
                self.policy.maximum_call_adjustment,
                0.03 + 0.10 * composite_confidence,
            )
            put_adjustment = min(
                self.policy.maximum_put_adjustment,
                0.05 + 0.15 * composite_confidence,
            )
            preferred_direction = "PUT"
            rationale.append("cross-asset intelligence favors bearish exposure")
        else:
            call_adjustment = 0.0
            put_adjustment = 0.0
            preferred_direction = "NEUTRAL"
            rationale.append("cross-asset intelligence is directionally neutral")

        if systemic_risk_level == "HIGH":
            position_multiplier = (
                self.policy.high_systemic_risk_position_multiplier
            )
            rationale.append("high systemic risk requires reduced position size")
        elif systemic_risk_level == "ELEVATED":
            position_multiplier = (
                self.policy.elevated_systemic_risk_position_multiplier
            )
            rationale.append(
                "elevated systemic risk requires moderated position size"
            )
        else:
            position_multiplier = self.policy.normal_position_multiplier

        if opportunity_regime == "SECURITY_SELECTION":
            confidence_multiplier = self.policy.high_confidence_multiplier
            rationale.append(
                "high dispersion and low correlation support selection alpha"
            )
        elif opportunity_regime in {
            "MACRO_DOMINATED",
            "CORRELATION_BREAKDOWN",
        }:
            confidence_multiplier = self.policy.low_confidence_multiplier
            rationale.append(
                "market structure reduces single-name signal reliability"
            )
        else:
            confidence_multiplier = 1.0

        allow_new_risk = governance_status != "EXCLUDED"
        if governance_status == "REVIEW":
            position_multiplier *= 0.75
            rationale.append("governance review status reduces risk budget")
        elif governance_status == "EXCLUDED":
            position_multiplier = 0.0
            confidence_multiplier = 0.0
            call_adjustment = 0.0
            put_adjustment = 0.0
            preferred_direction = "NEUTRAL"
            rationale.append("governance exclusion blocks new risk")

        return CrossAssetDecisionAdjustment(
            call_score_adjustment=call_adjustment,
            put_score_adjustment=put_adjustment,
            confidence_multiplier=confidence_multiplier,
            position_size_multiplier=position_multiplier,
            allow_new_risk=allow_new_risk,
            preferred_direction=preferred_direction,
            rationale=tuple(rationale),
        )

from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from .contracts import (
    CrossAssetIntelligenceGovernanceStatus,
    CrossAssetIntelligenceProfile,
)
from .decision_integration import CrossAssetDecisionIntegrationEngine
from .policy import CrossAssetIntelligencePolicy


class CrossAssetIntelligenceEngine:
    def __init__(
        self,
        policy: CrossAssetIntelligencePolicy | None = None,
    ) -> None:
        self.policy = policy or CrossAssetIntelligencePolicy()
        self.decision_engine = CrossAssetDecisionIntegrationEngine(
            self.policy
        )

    def evaluate(
        self,
        *,
        as_of_date: date,
        intermarket_profile: Mapping[str, Any],
        sector_profile: Mapping[str, Any],
        correlation_profile: Mapping[str, Any],
    ) -> CrossAssetIntelligenceProfile:
        source_governance = {
            "intermarket": str(
                intermarket_profile.get("governance_status", "EXCLUDED")
            ),
            "sector": str(
                sector_profile.get("governance_status", "EXCLUDED")
            ),
            "correlation": str(
                correlation_profile.get("governance_status", "EXCLUDED")
            ),
        }

        governance_status, reasons = self._govern(
            source_governance=source_governance,
            intermarket_confidence=self._float(
                intermarket_profile.get("confidence")
            ),
            sector_confidence=self._float(
                sector_profile.get("confidence")
            ),
            structure_confidence=self._float(
                correlation_profile.get("confidence")
            ),
        )

        intermarket_score = self._directional_score(
            str(intermarket_profile.get("market_state", "NEUTRAL"))
        )
        sector_score = self._sector_score(
            rotation_state=str(
                sector_profile.get("rotation_state", "MIXED_ROTATION")
            ),
            leadership_state=str(
                sector_profile.get("leadership_state", "BALANCED")
            ),
        )
        structure_score = self._structure_score(
            market_structure_state=str(
                correlation_profile.get(
                    "market_structure_state",
                    "BALANCED",
                )
            ),
            correlation_regime=str(
                correlation_profile.get(
                    "correlation_regime",
                    "NOT_OBSERVED",
                )
            ),
        )

        intermarket_confidence = self._float(
            intermarket_profile.get("confidence")
        )
        sector_confidence = self._float(
            sector_profile.get("confidence")
        )
        structure_confidence = self._float(
            correlation_profile.get("confidence")
        )

        weighted_score = (
            self.policy.intermarket_weight
            * intermarket_score
            * intermarket_confidence
            + self.policy.sector_weight
            * sector_score
            * sector_confidence
            + self.policy.structure_weight
            * structure_score
            * structure_confidence
        )

        confidence_weight = (
            self.policy.intermarket_weight * intermarket_confidence
            + self.policy.sector_weight * sector_confidence
            + self.policy.structure_weight * structure_confidence
        )
        normalized_score = (
            weighted_score / confidence_weight
            if confidence_weight > 0
            else 0.0
        )

        composite_risk_on = max(0.0, normalized_score)
        composite_risk_off = max(0.0, -normalized_score)
        composite_confidence = min(1.0, confidence_weight)

        if normalized_score >= self.policy.risk_on_threshold:
            macro_regime = "RISK_ON"
            tactical_bias = "BULLISH"
        elif normalized_score <= self.policy.risk_off_threshold:
            macro_regime = "RISK_OFF"
            tactical_bias = "BEARISH"
        else:
            macro_regime = "TRANSITIONAL"
            tactical_bias = "NEUTRAL"

        opportunity_regime = str(
            correlation_profile.get(
                "market_structure_state",
                "BALANCED",
            )
        )
        systemic_risk_level = self._systemic_risk_level(
            correlation_profile=correlation_profile,
            intermarket_profile=intermarket_profile,
        )

        adjustment = self.decision_engine.build_adjustment(
            tactical_bias=tactical_bias,
            systemic_risk_level=systemic_risk_level,
            opportunity_regime=opportunity_regime,
            composite_confidence=composite_confidence,
            governance_status=governance_status.value,
        )

        return CrossAssetIntelligenceProfile(
            as_of_date=as_of_date,
            intermarket_state=str(
                intermarket_profile.get("market_state", "NEUTRAL")
            ),
            intermarket_confidence=intermarket_confidence,
            sector_rotation_state=str(
                sector_profile.get("rotation_state", "MIXED_ROTATION")
            ),
            sector_leadership_state=str(
                sector_profile.get("leadership_state", "BALANCED")
            ),
            sector_confidence=sector_confidence,
            sector_leaders=tuple(
                sector_profile.get("leaders", ())
            ),
            sector_laggards=tuple(
                sector_profile.get("laggards", ())
            ),
            correlation_regime=str(
                correlation_profile.get(
                    "correlation_regime",
                    "NOT_OBSERVED",
                )
            ),
            dispersion_regime=str(
                correlation_profile.get(
                    "dispersion_regime",
                    "NOT_OBSERVED",
                )
            ),
            market_structure_state=opportunity_regime,
            structure_confidence=structure_confidence,
            composite_risk_on_score=composite_risk_on,
            composite_risk_off_score=composite_risk_off,
            composite_confidence=composite_confidence,
            macro_regime=macro_regime,
            tactical_bias=tactical_bias,
            opportunity_regime=opportunity_regime,
            systemic_risk_level=systemic_risk_level,
            decision_adjustment=adjustment,
            source_governance=source_governance,
            governance_status=governance_status,
            governance_reasons=tuple(reasons),
        )

    def _govern(
        self,
        *,
        source_governance: Mapping[str, str],
        intermarket_confidence: float,
        sector_confidence: float,
        structure_confidence: float,
    ) -> tuple[
        CrossAssetIntelligenceGovernanceStatus,
        list[str],
    ]:
        reasons: list[str] = []
        statuses = tuple(source_governance.values())

        if "EXCLUDED" in statuses:
            reasons.append("one or more source profiles are EXCLUDED")
            return (
                CrossAssetIntelligenceGovernanceStatus.EXCLUDED,
                reasons,
            )

        aggregate_confidence = (
            self.policy.intermarket_weight * intermarket_confidence
            + self.policy.sector_weight * sector_confidence
            + self.policy.structure_weight * structure_confidence
        )

        if aggregate_confidence < self.policy.minimum_confidence_review:
            reasons.append(
                f"aggregate confidence {aggregate_confidence:.6f} < "
                f"{self.policy.minimum_confidence_review:.6f}"
            )
            return (
                CrossAssetIntelligenceGovernanceStatus.EXCLUDED,
                reasons,
            )

        if (
            "REVIEW" in statuses
            or aggregate_confidence
            < self.policy.minimum_confidence_ready
        ):
            if "REVIEW" in statuses:
                reasons.append("one or more source profiles require REVIEW")
            if (
                aggregate_confidence
                < self.policy.minimum_confidence_ready
            ):
                reasons.append(
                    f"aggregate confidence {aggregate_confidence:.6f} < "
                    f"{self.policy.minimum_confidence_ready:.6f}"
                )
            return (
                CrossAssetIntelligenceGovernanceStatus.REVIEW,
                reasons,
            )

        return CrossAssetIntelligenceGovernanceStatus.READY, reasons

    @staticmethod
    def _directional_score(state: str) -> float:
        return {
            "RISK_ON": 1.0,
            "RISK_OFF": -1.0,
            "NEUTRAL": 0.0,
        }.get(state, 0.0)

    @staticmethod
    def _sector_score(
        *,
        rotation_state: str,
        leadership_state: str,
    ) -> float:
        rotation_component = {
            "BROAD_RISK_ON": 1.0,
            "NARROW_RISK_ON": 0.5,
            "DEFENSIVE_ROTATION": -1.0,
            "DEFENSIVE_BREADTH": -0.5,
            "MIXED_ROTATION": 0.0,
        }.get(rotation_state, 0.0)
        leadership_component = {
            "OFFENSIVE": 0.5,
            "DEFENSIVE": -0.5,
            "BALANCED": 0.0,
        }.get(leadership_state, 0.0)
        return max(
            -1.0,
            min(1.0, rotation_component + leadership_component),
        )

    @staticmethod
    def _structure_score(
        *,
        market_structure_state: str,
        correlation_regime: str,
    ) -> float:
        if market_structure_state == "CORRELATION_BREAKDOWN":
            return -0.5
        if market_structure_state == "SYSTEMIC":
            return -0.5
        if (
            market_structure_state == "SECURITY_SELECTION"
            and correlation_regime == "LOW_CORRELATION"
        ):
            return 0.25
        return 0.0

    @staticmethod
    def _systemic_risk_level(
        *,
        correlation_profile: Mapping[str, Any],
        intermarket_profile: Mapping[str, Any],
    ) -> str:
        structure_state = str(
            correlation_profile.get(
                "market_structure_state",
                "BALANCED",
            )
        )
        correlation_regime = str(
            correlation_profile.get(
                "correlation_regime",
                "NOT_OBSERVED",
            )
        )
        breakdown_ratio = float(
            correlation_profile.get(
                "correlation_breakdown_ratio",
                0.0,
            )
            or 0.0
        )
        intermarket_state = str(
            intermarket_profile.get("market_state", "NEUTRAL")
        )

        if (
            structure_state == "CORRELATION_BREAKDOWN"
            or breakdown_ratio >= 0.50
        ):
            return "HIGH"

        if (
            structure_state in {"SYSTEMIC", "MACRO_DOMINATED"}
            or correlation_regime == "HIGH_CORRELATION"
            or intermarket_state == "RISK_OFF"
        ):
            return "ELEVATED"

        return "NORMAL"

    @staticmethod
    def _float(value: Any) -> float:
        return float(value) if value is not None else 0.0

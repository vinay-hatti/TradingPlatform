from __future__ import annotations

from typing import Any, Iterable, Mapping

from trading_ai.strategy_engine.phase10_decision_integration_policy import Phase10DecisionIntegrationPolicy
from trading_ai.strategy_engine.phase10_decision_integration_profile import Phase10DecisionIntegrationProfile


class Phase10DecisionIntegrationService:
    def __init__(self, policy: Phase10DecisionIntegrationPolicy | None = None):
        self.policy = policy or Phase10DecisionIntegrationPolicy()
        self.policy.validate()

    @staticmethod
    def _value(obj: Any, name: str, default: Any = None) -> Any:
        if obj is None:
            return default
        if isinstance(obj, Mapping):
            return obj.get(name, default)
        return getattr(obj, name, default)

    @staticmethod
    def _profile_for_symbol(source: Any, symbol: str) -> Any:
        if source is None:
            return None
        if isinstance(source, Mapping):
            return source.get(symbol) or source.get(symbol.upper()) or source.get(symbol.lower())
        return source

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 90: return "A"
        if score >= 80: return "B"
        if score >= 70: return "C"
        if score >= 60: return "D"
        return "F"

    @staticmethod
    def _severity(allowed: bool, score: float) -> str:
        if allowed and score >= 75: return "LOW"
        if allowed: return "MODERATE"
        if score >= 50: return "SEVERE"
        return "CRITICAL"

    def analyze_symbol(
        self,
        symbol: str,
        *,
        legacy_strategy: str = "UNAVAILABLE",
        legacy_direction: str = "NEUTRAL",
        adaptive_profile: Any = None,
        learning_profile: Any = None,
        weighting_profile: Any = None,
        ensemble_profile: Any = None,
        online_adaptation_profile: Any = None,
        learning_state_registry_profile: Any = None,
        learning_state_promotion_profile: Any = None,
    ) -> Phase10DecisionIntegrationProfile:
        symbol = str(symbol or "").upper()
        warnings: list[str] = []
        rejections: list[str] = []

        adaptive_valid = bool(self._value(adaptive_profile, "valid", adaptive_profile is not None))
        adaptive_allowed = bool(self._value(adaptive_profile, "allowed", True))
        ensemble_valid = bool(self._value(ensemble_profile, "valid", ensemble_profile is not None))
        ensemble_allowed = bool(self._value(ensemble_profile, "allowed", True))

        selected_strategy = str(legacy_strategy or "UNAVAILABLE").upper()
        selected_direction = str(legacy_direction or "NEUTRAL").upper()
        if self.policy.prefer_ensemble_strategy and ensemble_valid:
            selected_strategy = str(self._value(ensemble_profile, "selected_strategy", selected_strategy) or selected_strategy).upper()
            selected_direction = str(self._value(ensemble_profile, "selected_direction", selected_direction) or selected_direction).upper()
        elif adaptive_valid:
            selected_strategy = str(self._value(adaptive_profile, "selected_strategy", selected_strategy) or selected_strategy).upper()

        ensemble_score = float(self._value(ensemble_profile, "ensemble_score", 0.0) or 0.0)
        meta_confidence = float(self._value(ensemble_profile, "meta_confidence_score", 0.0) or 0.0)
        adaptive_score = float(self._value(adaptive_profile, "selected_score", 0.0) or 0.0)
        adaptive_confidence = float(self._value(adaptive_profile, "selection_confidence_score", 0.0) or 0.0)

        allowed = True
        if self.policy.reject_on_invalid_ensemble and not ensemble_valid:
            allowed = False
            rejections.append("ENSEMBLE_DECISION_INVALID")
        if self.policy.require_ensemble_approval and ensemble_valid and not ensemble_allowed:
            allowed = False
            rejections.append("ENSEMBLE_DECISION_REJECTED")
        if ensemble_valid and ensemble_score < self.policy.minimum_ensemble_score:
            allowed = False
            rejections.append("ENSEMBLE_SCORE_BELOW_MINIMUM")
        if ensemble_valid and meta_confidence < self.policy.minimum_meta_confidence_score:
            allowed = False
            rejections.append("META_CONFIDENCE_BELOW_MINIMUM")
        if adaptive_valid and not adaptive_allowed:
            warnings.append("ADAPTIVE_SELECTION_NOT_APPROVED")
        if not ensemble_valid:
            warnings.append("ENSEMBLE_PROFILE_UNAVAILABLE")
            if not self.policy.preserve_legacy_selection_on_unavailable:
                allowed = False
                rejections.append("PHASE10_PROFILE_UNAVAILABLE")

        strategy_weight = 0.0
        weights = self._value(weighting_profile, "weights", ()) or ()
        for item in weights:
            if str(self._value(item, "strategy", "")).upper() == selected_strategy:
                strategy_weight = float(self._value(item, "normalized_weight", 0.0) or 0.0)
                break

        registry = learning_state_registry_profile
        score = ensemble_score if ensemble_valid else adaptive_score
        valid = bool(ensemble_valid or adaptive_valid)
        recommendation = (
            "USE_PHASE10_ENSEMBLE_SELECTION" if ensemble_valid and allowed
            else "USE_ADAPTIVE_SELECTION" if adaptive_valid and allowed
            else "RETAIN_LEGACY_SELECTION" if allowed
            else "REJECT_PHASE10_SELECTION"
        )
        return Phase10DecisionIntegrationProfile(
            symbol=symbol,
            valid=valid,
            allowed=allowed,
            adaptive_available=adaptive_profile is not None,
            learning_available=learning_profile is not None,
            ensemble_available=ensemble_profile is not None,
            online_adaptation_available=online_adaptation_profile is not None,
            learning_state_registry_available=registry is not None,
            selected_strategy=selected_strategy,
            selected_direction=selected_direction,
            adaptive_score=adaptive_score,
            adaptive_confidence_score=adaptive_confidence,
            ensemble_score=ensemble_score,
            meta_confidence_score=meta_confidence,
            consensus_ratio=float(self._value(ensemble_profile, "consensus_ratio", 0.0) or 0.0),
            strategy_weight=strategy_weight,
            adaptation_score=float(self._value(online_adaptation_profile, "adaptation_score", 0.0) or 0.0),
            learning_state_version=str(self._value(registry, "active_version", "UNAVAILABLE") or "UNAVAILABLE"),
            learning_state_champion_version=str(self._value(registry, "champion_version", "UNAVAILABLE") or "UNAVAILABLE"),
            learning_state_challenger_version=str(self._value(registry, "challenger_version", "UNAVAILABLE") or "UNAVAILABLE"),
            grade=self._grade(score),
            severity=self._severity(allowed, score),
            recommendation=recommendation,
            adaptive_strategy_profile=adaptive_profile,
            strategy_learning_profile=learning_profile,
            dynamic_strategy_weighting_profile=weighting_profile,
            ensemble_decision_profile=ensemble_profile,
            online_adaptation_profile=online_adaptation_profile,
            learning_state_registry_profile=registry,
            learning_state_promotion_profile=learning_state_promotion_profile,
            warnings=tuple(dict.fromkeys(warnings)),
            rejection_reasons=tuple(dict.fromkeys(rejections)),
            metadata={"legacy_strategy": legacy_strategy, "legacy_direction": legacy_direction},
        )

    def analyze(self, decisions: Iterable[Any], **sources: Any) -> dict[str, Phase10DecisionIntegrationProfile]:
        profiles = {}
        for decision in decisions:
            symbol = str(self._value(decision, "symbol", "")).upper()
            profiles[symbol] = self.analyze_symbol(
                symbol,
                legacy_strategy=self._value(decision, "strategy", "UNAVAILABLE"),
                legacy_direction=self._value(decision, "direction", "NEUTRAL"),
                adaptive_profile=self._profile_for_symbol(sources.get("adaptive_profiles"), symbol),
                learning_profile=self._profile_for_symbol(sources.get("learning_profiles"), symbol),
                weighting_profile=sources.get("dynamic_strategy_weighting_profile"),
                ensemble_profile=self._profile_for_symbol(sources.get("ensemble_profiles"), symbol),
                online_adaptation_profile=sources.get("online_adaptation_profile"),
                learning_state_registry_profile=sources.get("learning_state_registry_profile"),
                learning_state_promotion_profile=sources.get("learning_state_promotion_profile"),
            )
        return profiles

    def attach(self, decisions: Iterable[Any], profiles: Mapping[str, Phase10DecisionIntegrationProfile]) -> None:
        for decision in decisions:
            symbol = str(self._value(decision, "symbol", "")).upper()
            profile = profiles.get(symbol)
            if profile is None:
                continue
            values = {
                "phase10_valid": profile.valid,
                "phase10_allowed": profile.allowed,
                "adaptive_strategy_selected": profile.selected_strategy,
                "adaptive_strategy_score": profile.adaptive_score,
                "adaptive_strategy_confidence": profile.adaptive_confidence_score,
                "ensemble_selected_strategy": profile.selected_strategy,
                "ensemble_selected_direction": profile.selected_direction,
                "ensemble_decision_score": profile.ensemble_score,
                "ensemble_meta_confidence": profile.meta_confidence_score,
                "ensemble_consensus_ratio": profile.consensus_ratio,
                "dynamic_strategy_weight": profile.strategy_weight,
                "online_adaptation_score": profile.adaptation_score,
                "learning_state_version": profile.learning_state_version,
                "learning_state_champion_version": profile.learning_state_champion_version,
                "learning_state_challenger_version": profile.learning_state_challenger_version,
                "phase10_grade": profile.grade,
                "phase10_severity": profile.severity,
                "phase10_recommendation": profile.recommendation,
                "phase10_decision_integration_profile": profile,
            }
            if isinstance(decision, dict):
                decision.update(values)
                metadata = decision.setdefault("metadata", {})
            else:
                for name, value in values.items():
                    setattr(decision, name, value)
                metadata = getattr(decision, "metadata", None)
                if not isinstance(metadata, dict):
                    metadata = {}
                    setattr(decision, "metadata", metadata)
            metadata["phase10_decision_integration_profile"] = profile
            if not profile.allowed:
                if isinstance(decision, dict):
                    decision["allowed"] = False
                    decision.setdefault("rejection_reasons", []).extend(profile.rejection_reasons)
                else:
                    decision.allowed = False
                    decision.rejection_reasons.extend(x for x in profile.rejection_reasons if x not in decision.rejection_reasons)

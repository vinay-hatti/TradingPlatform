from __future__ import annotations

from math import isfinite, sqrt
from typing import Any, Iterable

from trading_ai.strategy_engine.ensemble_decision_policy import EnsembleDecisionPolicy
from trading_ai.strategy_engine.ensemble_decision_profile import (
    EnsembleComponentProfile,
    EnsembleDecisionProfile,
    EnsembleStrategyProfile,
)


class EnsembleDecisionEngine:
    """Fuses adaptive, learned, probability, regime, and execution evidence."""

    def __init__(self, policy: EnsembleDecisionPolicy | None = None):
        self.policy = policy or EnsembleDecisionPolicy()

    @staticmethod
    def _value(obj: Any, name: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    @staticmethod
    def _float(value: Any, default: float = 0.0) -> float:
        try:
            result = float(value)
            return result if isfinite(result) else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _bounded(value: float) -> float:
        return min(max(float(value), 0.0), 100.0)

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 85.0: return "A"
        if score >= 75.0: return "B"
        if score >= 65.0: return "C"
        if score >= 55.0: return "D"
        return "F"

    @staticmethod
    def _severity(score: float, allowed: bool) -> str:
        if not allowed and score < 40.0: return "CRITICAL"
        if not allowed: return "SEVERE"
        if score < 65.0: return "MODERATE"
        return "LOW"

    def _find(self, source: Any, strategy: str) -> Any:
        if source is None:
            return None
        if isinstance(source, dict):
            return source.get(strategy) or source.get(strategy.upper()) or source.get(strategy.lower())
        for item in source:
            if str(self._value(item, "strategy", "")).upper() == strategy.upper():
                return item
        return None

    def _component(self, name: str, strategy: str, source: Any, weight: float, score_names: tuple[str, ...], confidence_names: tuple[str, ...]) -> EnsembleComponentProfile:
        item = self._find(source, strategy)
        if item is None:
            return EnsembleComponentProfile(name, strategy, "UNKNOWN", 0.0, 0.0, weight, 0.0, False, False, {})
        score = next((self._value(item, key, None) for key in score_names if self._value(item, key, None) is not None), 0.0)
        confidence = next((self._value(item, key, None) for key in confidence_names if self._value(item, key, None) is not None), 50.0)
        score = self._bounded(self._float(score))
        confidence = self._bounded(self._float(confidence, 50.0))
        allowed = bool(self._value(item, "allowed", True))
        direction = str(self._value(item, "direction", self._value(item, "signal", "UNKNOWN")) or "UNKNOWN").upper()
        return EnsembleComponentProfile(
            name=name, strategy=strategy, direction=direction, score=score,
            confidence_score=confidence, weight=weight,
            weighted_score=round(score * weight, 4), available=True, allowed=allowed,
            metadata={"source_type": type(item).__name__},
        )

    def evaluate_strategy(self, symbol: str, strategy: str, *, adaptive: Any = None, learned: Any = None, probability: Any = None, regime: Any = None, execution: Any = None) -> EnsembleStrategyProfile:
        weights = self.policy.normalized_weights()
        components = (
            self._component("adaptive", strategy, adaptive, weights["adaptive"], ("adaptive_score", "selected_score", "score"), ("confidence_score", "selection_confidence_score")),
            self._component("learned", strategy, learned, weights["learned"], ("performance_score", "score"), ("confidence_score",)),
            self._component("probability", strategy, probability, weights["probability"], ("calibrated_probability_score", "probability_score", "score"), ("confidence_score", "calibration_confidence")),
            self._component("regime", strategy, regime, weights["regime"], ("regime_score", "score"), ("confidence_score",)),
            self._component("execution", strategy, execution, weights["execution"], ("execution_score", "score"), ("confidence_score",)),
        )
        available = tuple(c for c in components if c.available)
        warnings: list[str] = []
        rejections: list[str] = []
        if len(available) < self.policy.minimum_component_count:
            warnings.append("INSUFFICIENT_ENSEMBLE_COMPONENTS")
            rejections.append("COMPONENT_COUNT_BELOW_POLICY")
        available_weight = sum(c.weight for c in available)
        ensemble_score = sum(c.weighted_score for c in available) / available_weight if available_weight else 0.0
        confidence = sum(c.confidence_score * c.weight for c in available) / available_weight if available_weight else 0.0
        scores = [c.score for c in available]
        mean = sum(scores) / len(scores) if scores else 0.0
        dispersion = sqrt(sum((x - mean) ** 2 for x in scores) / len(scores)) if scores else 0.0
        allowed_count = sum(1 for c in available if c.allowed)
        consensus = allowed_count / len(available) if available else 0.0
        known_directions = {c.direction for c in available if c.direction not in {"", "UNKNOWN", "NEUTRAL"}}
        direction = next(iter(known_directions), "UNKNOWN") if len(known_directions) == 1 else "MIXED"
        if len(known_directions) > 1:
            warnings.append("ENSEMBLE_DIRECTION_CONFLICT")
            if self.policy.reject_on_direction_conflict:
                rejections.append("DIRECTION_CONFLICT")
        if ensemble_score < self.policy.minimum_ensemble_score:
            rejections.append("ENSEMBLE_SCORE_BELOW_POLICY")
        if confidence < self.policy.minimum_meta_confidence:
            rejections.append("META_CONFIDENCE_BELOW_POLICY")
        if consensus < self.policy.minimum_consensus_ratio:
            rejections.append("CONSENSUS_BELOW_POLICY")
        if dispersion > self.policy.maximum_score_dispersion:
            warnings.append("HIGH_COMPONENT_DISPERSION")
            rejections.append("COMPONENT_DISPERSION_ABOVE_POLICY")
        allowed = not rejections
        recommendation = "SELECT_ENSEMBLE_STRATEGY" if allowed else ("FALLBACK_TO_ADAPTIVE_SELECTION" if self.policy.fallback_to_adaptive_selection else "REJECT")
        return EnsembleStrategyProfile(
            symbol=symbol, strategy=strategy.upper(), direction=direction,
            ensemble_score=round(self._bounded(ensemble_score), 4),
            meta_confidence_score=round(self._bounded(confidence), 4),
            consensus_ratio=round(consensus, 4), score_dispersion=round(dispersion, 4),
            component_count=len(available), allowed_component_count=allowed_count,
            allowed=allowed, grade=self._grade(ensemble_score), severity=self._severity(ensemble_score, allowed),
            recommendation=recommendation, components=components,
            warnings=tuple(dict.fromkeys(warnings)), rejection_reasons=tuple(dict.fromkeys(rejections)),
            metadata={"weights": weights, "available_weight": round(available_weight, 6)},
        )

    def decide(self, symbol: str, strategies: Iterable[str], **sources: Any) -> EnsembleDecisionProfile:
        evaluated = tuple(sorted(
            (self.evaluate_strategy(symbol, strategy, **sources) for strategy in strategies),
            key=lambda p: (p.allowed, p.ensemble_score, p.meta_confidence_score), reverse=True,
        ))
        selected = next((p for p in evaluated if p.allowed), None)
        best = selected or (evaluated[0] if evaluated else None)
        warnings = tuple(dict.fromkeys(w for p in evaluated for w in p.warnings))
        rejections = tuple(dict.fromkeys(r for p in evaluated for r in p.rejection_reasons))
        score = best.ensemble_score if best else 0.0
        confidence = best.meta_confidence_score if best else 0.0
        consensus = best.consensus_ratio if best else 0.0
        allowed = selected is not None
        return EnsembleDecisionProfile(
            symbol=symbol, valid=bool(evaluated), allowed=allowed,
            selected_strategy=selected.strategy if selected else None,
            selected_direction=selected.direction if selected else None,
            ensemble_score=score, meta_confidence_score=confidence, consensus_ratio=consensus,
            grade=self._grade(score), severity=self._severity(score, allowed),
            recommendation="USE_ENSEMBLE_DECISION" if allowed else "FALLBACK_TO_ADAPTIVE_SELECTION",
            strategies=evaluated, warnings=warnings, rejection_reasons=rejections,
            metadata={"strategy_count": len(evaluated), "allowed_strategy_count": sum(1 for p in evaluated if p.allowed)},
        )

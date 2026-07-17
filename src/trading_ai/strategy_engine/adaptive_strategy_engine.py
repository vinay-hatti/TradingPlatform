from __future__ import annotations

from math import isfinite
from typing import Any, Iterable

from trading_ai.strategy_engine.adaptive_strategy_policy import AdaptiveStrategyPolicy
from trading_ai.strategy_engine.adaptive_strategy_profile import (
    AdaptiveStrategyCandidateProfile,
    AdaptiveStrategySelectionProfile,
    StrategyPerformanceProfile,
)


class AdaptiveStrategyEngine:
    """Context-aware overlay for the existing rule-based StrategySelector."""

    def __init__(self, policy: AdaptiveStrategyPolicy | None = None):
        self.policy = policy or AdaptiveStrategyPolicy()

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
    def _bounded(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
        return min(max(float(value), lower), upper)

    def _performance_profile(self, strategy: str, profiles: Any) -> StrategyPerformanceProfile | None:
        if profiles is None:
            return None
        source = profiles.get(strategy) if isinstance(profiles, dict) else None
        if source is None and not isinstance(profiles, dict):
            for item in profiles:
                if str(self._value(item, "strategy", "")).upper() == strategy.upper():
                    source = item
                    break
        if source is None:
            return None
        if isinstance(source, StrategyPerformanceProfile):
            return source
        return StrategyPerformanceProfile(
            strategy=strategy,
            observation_count=int(self._float(self._value(source, "observation_count", 0))),
            win_rate=self._float(self._value(source, "win_rate", 0.0)),
            average_return=self._float(self._value(source, "average_return", 0.0)),
            profit_factor=self._float(self._value(source, "profit_factor", 0.0)),
            maximum_drawdown_pct=abs(self._float(self._value(source, "maximum_drawdown_pct", 0.0))),
            sharpe_ratio=self._float(self._value(source, "sharpe_ratio", 0.0)),
            calibration_score=self._float(self._value(source, "calibration_score", 50.0), 50.0),
            execution_score=self._float(self._value(source, "execution_score", 50.0), 50.0),
            context_observation_count=int(self._float(self._value(source, "context_observation_count", 0))),
            context_win_rate=self._value(source, "context_win_rate", None),
            context_average_return=self._value(source, "context_average_return", None),
            metadata=dict(self._value(source, "metadata", {}) or {}),
        )

    def _performance_score(self, p: StrategyPerformanceProfile) -> float:
        win = self._bounded(p.win_rate * 100.0)
        returns = self._bounded(50.0 + p.average_return * 250.0)
        profit_factor = self._bounded(p.profit_factor * 40.0)
        drawdown = self._bounded(100.0 - p.maximum_drawdown_pct * 300.0)
        sharpe = self._bounded(50.0 + p.sharpe_ratio * 20.0)
        return round(0.30 * win + 0.25 * returns + 0.20 * profit_factor + 0.15 * drawdown + 0.10 * sharpe, 4)

    def _regime_score(self, p: StrategyPerformanceProfile) -> float:
        if p.context_observation_count < self.policy.minimum_context_observations:
            return 50.0
        win_rate = p.context_win_rate if p.context_win_rate is not None else p.win_rate
        avg_return = p.context_average_return if p.context_average_return is not None else p.average_return
        return round(0.60 * self._bounded(self._float(win_rate) * 100.0) + 0.40 * self._bounded(50.0 + self._float(avg_return) * 250.0), 4)

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 85.0: return "A"
        if score >= 75.0: return "B"
        if score >= 65.0: return "C"
        if score >= 50.0: return "D"
        return "F"

    @staticmethod
    def _severity(score: float, allowed: bool) -> str:
        if not allowed and score < 35.0: return "CRITICAL"
        if not allowed: return "SEVERE"
        if score < 60.0: return "MODERATE"
        return "LOW"

    def evaluate_candidate(self, candidate: Any, performance_profiles: Any = None) -> AdaptiveStrategyCandidateProfile:
        strategy = str(self._value(candidate, "strategy", "UNKNOWN") or "UNKNOWN").upper()
        original = self._bounded(self._float(self._value(candidate, "score", 0.0)))
        performance = self._performance_profile(strategy, performance_profiles)
        warnings: list[str] = []
        rejections: list[str] = []

        if performance is None or performance.observation_count < self.policy.minimum_strategy_observations:
            performance_score = 50.0
            regime_score = 50.0
            calibration_score = 50.0
            execution_score = self._bounded(self._float(self._value(candidate, "execution_score", 50.0), 50.0))
            observations = 0 if performance is None else performance.observation_count
            context_observations = 0 if performance is None else performance.context_observation_count
            warnings.append("INSUFFICIENT_STRATEGY_HISTORY")
        else:
            performance_score = self._performance_score(performance)
            regime_score = self._regime_score(performance)
            calibration_score = self._bounded(performance.calibration_score)
            execution_score = self._bounded(performance.execution_score)
            observations = performance.observation_count
            context_observations = performance.context_observation_count
            if context_observations < self.policy.minimum_context_observations:
                warnings.append("INSUFFICIENT_CONTEXT_HISTORY")
            if performance.maximum_drawdown_pct >= self.policy.severe_drawdown_pct:
                rejections.append("SEVERE_STRATEGY_DRAWDOWN")
            if performance.profit_factor < self.policy.minimum_profit_factor:
                rejections.append("PROFIT_FACTOR_BELOW_POLICY")
            if performance.win_rate < self.policy.minimum_win_rate:
                rejections.append("WIN_RATE_BELOW_POLICY")

        weights = self.policy.normalized_weights()
        adaptive = (
            original * weights["prior"]
            + performance_score * weights["performance"]
            + regime_score * weights["regime"]
            + calibration_score * weights["calibration"]
            + execution_score * weights["execution"]
        )
        raw_adjustment = adaptive - original
        adjustment = min(max(raw_adjustment, -self.policy.maximum_negative_adjustment), self.policy.maximum_positive_adjustment)
        adaptive_score = self._bounded(original + adjustment)
        confidence = self._bounded(min(100.0, observations / max(self.policy.minimum_strategy_observations, 1) * 60.0 + context_observations / max(self.policy.minimum_context_observations, 1) * 40.0))
        allowed = adaptive_score >= self.policy.minimum_allowed_score and confidence >= self.policy.minimum_confidence_score
        if self.policy.reject_on_severe_performance and rejections:
            allowed = False
        if confidence < self.policy.minimum_confidence_score:
            rejections.append("ADAPTIVE_CONFIDENCE_BELOW_POLICY")
        if adaptive_score < self.policy.minimum_allowed_score:
            rejections.append("ADAPTIVE_SCORE_BELOW_POLICY")

        recommendation = "SELECT" if allowed else ("RETAIN_PRIOR" if self.policy.fallback_to_prior and not rejections else "REJECT")
        return AdaptiveStrategyCandidateProfile(
            symbol=str(self._value(candidate, "symbol", "")), strategy=strategy,
            direction=str(self._value(candidate, "direction", "NEUTRAL")),
            market_regime=str(self._value(candidate, "market_regime", "UNKNOWN")),
            volatility_regime=str(self._value(candidate, "volatility_regime", "UNKNOWN")),
            original_score=round(original, 4), prior_score=round(original, 4),
            performance_score=performance_score, regime_score=regime_score,
            calibration_score=calibration_score, execution_score=execution_score,
            adaptive_adjustment=round(adjustment, 4), adaptive_score=round(adaptive_score, 4),
            confidence_score=round(confidence, 4), observation_count=observations,
            context_observation_count=context_observations, allowed=allowed,
            grade=self._grade(adaptive_score), severity=self._severity(adaptive_score, allowed),
            recommendation=recommendation, warnings=tuple(dict.fromkeys(warnings)),
            rejection_reasons=tuple(dict.fromkeys(rejections)),
            metadata={"weights": weights, "policy": "AdaptiveStrategyPolicy"},
        )

    def select(self, symbol: str, candidates: Iterable[Any], performance_profiles: Any = None) -> AdaptiveStrategySelectionProfile:
        evaluated = tuple(sorted(
            (self.evaluate_candidate(candidate, performance_profiles) for candidate in candidates),
            key=lambda item: (item.allowed, item.adaptive_score, item.confidence_score), reverse=True,
        ))
        warnings = tuple(dict.fromkeys(w for item in evaluated for w in item.warnings))
        rejections = tuple(dict.fromkeys(r for item in evaluated for r in item.rejection_reasons))
        selected = next((item for item in evaluated if item.allowed), None)
        valid = bool(evaluated)
        allowed = selected is not None
        score = selected.adaptive_score if selected else (evaluated[0].adaptive_score if evaluated else 0.0)
        confidence = selected.confidence_score if selected else (evaluated[0].confidence_score if evaluated else 0.0)
        return AdaptiveStrategySelectionProfile(
            symbol=symbol, valid=valid, allowed=allowed,
            selected_strategy=selected.strategy if selected else None,
            selected_score=score, selection_confidence_score=confidence,
            grade=self._grade(score), severity=self._severity(score, allowed),
            recommendation="USE_ADAPTIVE_SELECTION" if allowed else "FALLBACK_TO_RULE_BASED_SELECTION",
            candidates=evaluated, warnings=warnings, rejection_reasons=rejections,
            metadata={"candidate_count": len(evaluated), "allowed_candidate_count": sum(1 for item in evaluated if item.allowed)},
        )

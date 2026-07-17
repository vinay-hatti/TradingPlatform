from __future__ import annotations

from collections import defaultdict
from datetime import date
from math import exp, isfinite, log, sqrt
from statistics import pstdev
from typing import Iterable

from trading_ai.strategy_engine.strategy_learning_policy import StrategyLearningPolicy
from trading_ai.strategy_engine.strategy_learning_profile import (
    DynamicStrategyWeightProfile,
    StrategyLearningProfile,
    StrategyLearningSegmentProfile,
    StrategyOutcomeRecord,
    StrategyWeightingProfile,
)


class StrategyLearningEngine:
    """Learn governed strategy performance and derive dynamic strategy weights."""

    def __init__(self, policy: StrategyLearningPolicy | None = None):
        self.policy = policy or StrategyLearningPolicy()

    @staticmethod
    def _bounded(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
        return min(max(float(value), lower), upper)

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

    def _weights(self, records: list[StrategyOutcomeRecord], as_of: date) -> list[float]:
        half_life = max(float(self.policy.recency_half_life_days), 1.0)
        return [exp(-log(2.0) * max((as_of - record.outcome_date).days, 0) / half_life) for record in records]

    @staticmethod
    def _effective_sample_size(weights: list[float]) -> float:
        total = sum(weights)
        denominator = sum(weight * weight for weight in weights)
        return (total * total / denominator) if denominator > 0.0 else 0.0

    def _statistics(self, records: list[StrategyOutcomeRecord], as_of: date) -> dict[str, float]:
        if not records:
            return {name: 0.0 for name in (
                "effective_sample_size", "win_rate", "average_return", "volatility", "profit_factor",
                "maximum_drawdown_pct", "sharpe_ratio", "calibration_score", "execution_score",
                "stability_score", "recency_score", "performance_score",
            )}
        weights = self._weights(records, as_of)
        total = sum(weights) or 1.0
        returns = [record.realized_return for record in records]
        avg_return = sum(weight * value for weight, value in zip(weights, returns)) / total
        variance = sum(weight * (value - avg_return) ** 2 for weight, value in zip(weights, returns)) / total
        volatility = sqrt(max(variance, 0.0))
        win_rate = sum(weight for weight, record in zip(weights, records) if record.won) / total
        gains = sum(weight * max(record.realized_return, 0.0) for weight, record in zip(weights, records))
        losses = abs(sum(weight * min(record.realized_return, 0.0) for weight, record in zip(weights, records)))
        profit_factor = gains / losses if losses > 1e-12 else (10.0 if gains > 0.0 else 0.0)
        equity = peak = 1.0
        maximum_drawdown = 0.0
        for record in sorted(records, key=lambda item: item.outcome_date):
            equity *= max(1.0 + record.realized_return, 1e-6)
            peak = max(peak, equity)
            maximum_drawdown = max(maximum_drawdown, (peak - equity) / peak)
        sharpe = avg_return / volatility * sqrt(252.0) if volatility > 1e-12 else 0.0
        calibration = sum(weight * record.calibration_score for weight, record in zip(weights, records)) / total
        execution = sum(weight * record.execution_score for weight, record in zip(weights, records)) / total
        effective = self._effective_sample_size(weights)
        return_stability = self._bounded(100.0 - volatility * 300.0)
        drawdown_stability = self._bounded(100.0 - maximum_drawdown * 300.0)
        directional_stability = self._bounded(100.0 - pstdev(returns) * 250.0) if len(returns) > 1 else 50.0
        stability = 0.40 * return_stability + 0.40 * drawdown_stability + 0.20 * directional_stability
        recent_weight_share = sum(weight for weight, record in zip(weights, records) if (as_of - record.outcome_date).days <= 90) / total
        recency = self._bounded(recent_weight_share * 100.0)
        performance = (
            0.30 * self._bounded(win_rate * 100.0)
            + 0.25 * self._bounded(50.0 + avg_return * 300.0)
            + 0.20 * self._bounded(profit_factor * 35.0)
            + 0.15 * self._bounded(100.0 - maximum_drawdown * 300.0)
            + 0.10 * self._bounded(50.0 + sharpe * 8.0)
        )
        return {
            "effective_sample_size": effective,
            "win_rate": win_rate,
            "average_return": avg_return,
            "volatility": volatility,
            "profit_factor": profit_factor,
            "maximum_drawdown_pct": maximum_drawdown,
            "sharpe_ratio": sharpe,
            "calibration_score": calibration,
            "execution_score": execution,
            "stability_score": stability,
            "recency_score": recency,
            "performance_score": performance,
        }

    def _segment(self, strategy: str, key: str, value: str, records: list[StrategyOutcomeRecord], as_of: date) -> StrategyLearningSegmentProfile:
        stats = self._statistics(records, as_of)
        warnings = []
        valid = len(records) >= self.policy.minimum_segment_observations and stats["effective_sample_size"] >= self.policy.minimum_effective_sample_size
        if not valid:
            warnings.append("INSUFFICIENT_SEGMENT_HISTORY")
        return StrategyLearningSegmentProfile(
            strategy=strategy, segment_key=key, segment_value=value,
            observation_count=len(records), effective_sample_size=round(stats["effective_sample_size"], 4),
            weighted_win_rate=round(stats["win_rate"], 6), weighted_average_return=round(stats["average_return"], 6),
            weighted_return_volatility=round(stats["volatility"], 6), profit_factor=round(stats["profit_factor"], 6),
            maximum_drawdown_pct=round(stats["maximum_drawdown_pct"], 6), sharpe_ratio=round(stats["sharpe_ratio"], 6),
            stability_score=round(stats["stability_score"], 4), recency_score=round(stats["recency_score"], 4),
            performance_score=round(stats["performance_score"], 4), valid=valid,
            warnings=tuple(warnings), metadata={"policy": "StrategyLearningPolicy"},
        )

    def learn(self, records: Iterable[StrategyOutcomeRecord], as_of_date: date | None = None) -> dict[str, StrategyLearningProfile]:
        as_of = as_of_date or date.today()
        grouped: dict[str, list[StrategyOutcomeRecord]] = defaultdict(list)
        for record in records:
            grouped[record.strategy.upper()].append(record)
        profiles: dict[str, StrategyLearningProfile] = {}
        for strategy, strategy_records in grouped.items():
            stats = self._statistics(strategy_records, as_of)
            warnings: list[str] = []
            rejections: list[str] = []
            valid = len(strategy_records) >= self.policy.minimum_observations
            if not valid:
                warnings.append("INSUFFICIENT_STRATEGY_HISTORY")
            if stats["effective_sample_size"] < self.policy.minimum_effective_sample_size:
                warnings.append("LOW_EFFECTIVE_SAMPLE_SIZE")
            allowed = valid and stats["effective_sample_size"] >= self.policy.minimum_effective_sample_size
            if not allowed:
                rejections.append("STRATEGY_LEARNING_NOT_GOVERNANCE_READY")
            segments: list[StrategyLearningSegmentProfile] = []
            for key in self.policy.context_keys:
                values: dict[str, list[StrategyOutcomeRecord]] = defaultdict(list)
                for record in strategy_records:
                    value = str(getattr(record, key, "UNKNOWN") or "UNKNOWN").upper()
                    if value != "UNKNOWN" or self.policy.preserve_unknown_context:
                        values[value].append(record)
                for value, segment_records in sorted(values.items()):
                    segments.append(self._segment(strategy, key, value, segment_records, as_of))
            confidence = self._bounded(
                min(60.0, len(strategy_records) / max(self.policy.minimum_observations, 1) * 60.0)
                + min(40.0, stats["effective_sample_size"] / max(self.policy.minimum_effective_sample_size, 1.0) * 40.0)
            )
            score = stats["performance_score"]
            profiles[strategy] = StrategyLearningProfile(
                strategy=strategy, valid=valid, allowed=allowed, observation_count=len(strategy_records),
                effective_sample_size=round(stats["effective_sample_size"], 4), weighted_win_rate=round(stats["win_rate"], 6),
                weighted_average_return=round(stats["average_return"], 6), weighted_return_volatility=round(stats["volatility"], 6),
                profit_factor=round(stats["profit_factor"], 6), maximum_drawdown_pct=round(stats["maximum_drawdown_pct"], 6),
                sharpe_ratio=round(stats["sharpe_ratio"], 6), calibration_score=round(stats["calibration_score"], 4),
                execution_score=round(stats["execution_score"], 4), stability_score=round(stats["stability_score"], 4),
                recency_score=round(stats["recency_score"], 4), performance_score=round(score, 4),
                confidence_score=round(confidence, 4), grade=self._grade(score), severity=self._severity(score, allowed),
                segments=tuple(segments), warnings=tuple(dict.fromkeys(warnings)),
                rejection_reasons=tuple(dict.fromkeys(rejections)), metadata={"as_of_date": as_of.isoformat()},
            )
        return profiles

    def dynamic_weights(self, profiles: Iterable[StrategyLearningProfile], prior_weights: dict[str, float] | None = None) -> StrategyWeightingProfile:
        items = list(profiles)
        priors = {str(k).upper(): max(float(v), 0.0) for k, v in (prior_weights or {}).items()}
        equal_prior = 1.0 / len(items) if items else 0.0
        components = self.policy.normalized_components()
        raw: list[tuple[StrategyLearningProfile, float, float, float, float]] = []
        for profile in items:
            prior = priors.get(profile.strategy.upper(), equal_prior)
            performance = profile.performance_score / 100.0
            stability = profile.stability_score / 100.0
            recency = profile.recency_score / 100.0
            score = prior * components["prior"] + performance * components["performance"] + stability * components["stability"] + recency * components["recency"]
            score = min(max(score, self.policy.minimum_weight), self.policy.maximum_weight)
            if not profile.allowed:
                score = self.policy.minimum_weight
            raw.append((profile, prior, performance, stability, recency, score))
        total = sum(item[5] for item in raw)
        weights: list[DynamicStrategyWeightProfile] = []
        for profile, prior, performance, stability, recency, score in raw:
            normalized = score / total if total > 0.0 else 0.0
            allowed = profile.allowed
            weights.append(DynamicStrategyWeightProfile(
                strategy=profile.strategy, valid=profile.valid, allowed=allowed,
                prior_weight=round(prior, 6), performance_component=round(performance, 6),
                stability_component=round(stability, 6), recency_component=round(recency, 6),
                raw_weight=round(score, 6), normalized_weight=round(normalized, 6),
                confidence_score=profile.confidence_score, grade=profile.grade,
                severity=profile.severity, warnings=profile.warnings, rejection_reasons=profile.rejection_reasons,
                metadata={"component_weights": components},
            ))
        concentration = sum(item.normalized_weight ** 2 for item in weights)
        effective = 1.0 / concentration if concentration > 0.0 else 0.0
        allowed = bool(weights) and any(item.allowed for item in weights)
        score = self._bounded(effective / max(len(weights), 1) * 100.0)
        return StrategyWeightingProfile(
            valid=bool(weights), allowed=allowed, strategy_count=len(weights),
            total_weight=round(sum(item.normalized_weight for item in weights), 6),
            weights=tuple(sorted(weights, key=lambda item: item.normalized_weight, reverse=True)),
            concentration_score=round(concentration, 6), effective_strategy_count=round(effective, 4),
            grade=self._grade(score), severity=self._severity(score, allowed),
            warnings=(), rejection_reasons=() if allowed else ("NO_GOVERNANCE_READY_STRATEGIES",),
            metadata={"policy": "StrategyLearningPolicy"},
        )

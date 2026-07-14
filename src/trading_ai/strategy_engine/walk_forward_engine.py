from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from typing import Any

import numpy as np

from .walk_forward_policy import WalkForwardPolicy
from .walk_forward_profile import WalkForwardProfile, WalkForwardWindowResult
from .walk_forward_splitter import InstitutionalWalkForwardSplitter

Evaluator = Callable[[Sequence[Any], dict[str, Any]], dict[str, float]]


class InstitutionalWalkForwardEngine:
    """Rolling train/validation/test optimizer with purge and embargo support."""

    def __init__(self, policy: WalkForwardPolicy | None = None) -> None:
        self.policy = policy or WalkForwardPolicy()
        self.splitter = InstitutionalWalkForwardSplitter(self.policy)

    def run(
        self,
        observations: Sequence[Any],
        parameter_grid: Iterable[dict[str, Any]],
        evaluator: Evaluator,
    ) -> WalkForwardProfile:
        windows = self.splitter.split(len(observations))
        profile = WalkForwardProfile(windows=windows, window_count=len(windows))
        if len(windows) < self.policy.minimum_windows:
            profile.rejection_reasons.append("INSUFFICIENT_WALK_FORWARD_WINDOWS")
            profile.risk_severity = "CRITICAL"
            return profile

        parameters = [dict(item) for item in parameter_grid]
        if not parameters:
            profile.rejection_reasons.append("EMPTY_PARAMETER_GRID")
            profile.risk_severity = "CRITICAL"
            return profile

        for window in windows:
            train = observations[window.train_start:window.train_end]
            validation = observations[window.validation_start:window.validation_end]
            test = observations[window.test_start:window.test_end]
            if (
                len(train) < self.policy.minimum_train_observations
                or len(validation) < self.policy.minimum_validation_observations
                or len(test) < self.policy.minimum_test_observations
            ):
                continue

            candidates: list[tuple[float, dict[str, Any], dict[str, float], dict[str, float]]] = []
            for params in parameters:
                train_metrics = evaluator(train, params)
                validation_metrics = evaluator(validation, params)
                score = self._selection_score(train_metrics, validation_metrics)
                candidates.append((score, params, train_metrics, validation_metrics))
            candidates.sort(key=lambda item: (item[0], str(sorted(item[1].items()))), reverse=True)
            score, selected, train_metrics, validation_metrics = candidates[0]
            test_metrics = evaluator(test, selected)
            degradation = self._degradation(validation_metrics.get("score", score), test_metrics.get("score", 0.0))
            result = WalkForwardWindowResult(
                window_id=window.window_id,
                selected_parameters=selected,
                train_score=float(train_metrics.get("score", 0.0)),
                validation_score=float(validation_metrics.get("score", 0.0)),
                test_score=float(test_metrics.get("score", 0.0)),
                train_return=float(train_metrics.get("return", 0.0)),
                validation_return=float(validation_metrics.get("return", 0.0)),
                test_return=float(test_metrics.get("return", 0.0)),
                train_sharpe=float(train_metrics.get("sharpe", 0.0)),
                validation_sharpe=float(validation_metrics.get("sharpe", 0.0)),
                test_sharpe=float(test_metrics.get("sharpe", 0.0)),
                test_max_drawdown_pct=abs(float(test_metrics.get("max_drawdown_pct", 0.0))),
                degradation_pct=degradation,
            )
            if result.test_max_drawdown_pct > self.policy.maximum_oos_drawdown_pct:
                result.valid = False
                result.rejection_reasons.append("OOS_DRAWDOWN_LIMIT_EXCEEDED")
            if degradation > self.policy.maximum_degradation_pct:
                result.warnings.append("OOS_DEGRADATION_ELEVATED")
            profile.results.append(result)

        self._finalize(profile)
        return profile

    def _selection_score(self, train: dict[str, float], validation: dict[str, float]) -> float:
        # Validation is authoritative; training is retained as a modest stability prior.
        return 0.25 * float(train.get("score", 0.0)) + 0.75 * float(validation.get("score", 0.0))

    @staticmethod
    def _degradation(validation_score: float, test_score: float) -> float:
        denominator = max(abs(validation_score), 1e-12)
        return max(0.0, (validation_score - test_score) / denominator)

    def _finalize(self, profile: WalkForwardProfile) -> None:
        results = profile.results
        profile.completed_window_count = len(results)
        if len(results) < self.policy.minimum_windows:
            profile.rejection_reasons.append("INSUFFICIENT_COMPLETED_WINDOWS")
            profile.risk_severity = "CRITICAL"
            return

        profile.aggregate_oos_return = float(np.prod([1.0 + r.test_return for r in results]) - 1.0)
        profile.average_oos_sharpe = float(np.mean([r.test_sharpe for r in results]))
        profile.worst_oos_drawdown_pct = max(r.test_max_drawdown_pct for r in results)
        profile.average_degradation_pct = float(np.mean([r.degradation_pct for r in results]))
        profile.parameter_stability_score = self._parameter_stability(results)
        profile.window_consistency_score = 100.0 * sum(r.test_return > 0 for r in results) / len(results)
        profile.walk_forward_score = self._score(profile)
        profile.walk_forward_grade = self._grade(profile.walk_forward_score)
        profile.risk_severity = self._severity(profile)
        profile.valid = True
        profile.allowed = not any(not r.valid for r in results)
        if profile.average_oos_sharpe < self.policy.minimum_oos_sharpe:
            profile.allowed = False
            profile.rejection_reasons.append("MINIMUM_OOS_SHARPE_NOT_MET")
        if profile.parameter_stability_score < self.policy.minimum_parameter_stability_score:
            profile.warnings.append("PARAMETER_INSTABILITY")
            if self.policy.reject_critical_instability and profile.parameter_stability_score < 25.0:
                profile.allowed = False
                profile.rejection_reasons.append("CRITICAL_PARAMETER_INSTABILITY")

    @staticmethod
    def _parameter_stability(results: list[WalkForwardWindowResult]) -> float:
        signatures = [tuple(sorted(r.selected_parameters.items())) for r in results]
        dominant = Counter(signatures).most_common(1)[0][1]
        return 100.0 * dominant / len(signatures)

    def _score(self, profile: WalkForwardProfile) -> float:
        w = self.policy.objective_weights
        return_component = min(100.0, max(0.0, 50.0 + profile.aggregate_oos_return * 100.0))
        sharpe_component = min(100.0, max(0.0, 50.0 + profile.average_oos_sharpe * 20.0))
        drawdown_component = max(0.0, 100.0 * (1.0 - profile.worst_oos_drawdown_pct / max(self.policy.maximum_oos_drawdown_pct, 1e-12)))
        degradation_component = max(0.0, 100.0 * (1.0 - profile.average_degradation_pct))
        score = (
            w.get("return", 0.30) * return_component
            + w.get("sharpe", 0.25) * sharpe_component
            + w.get("drawdown", 0.20) * drawdown_component
            + w.get("stability", 0.15) * profile.parameter_stability_score
            + w.get("consistency", 0.10) * profile.window_consistency_score
        )
        return round(min(100.0, max(0.0, score * (0.75 + 0.25 * degradation_component / 100.0))), 2)

    @staticmethod
    def _grade(score: float) -> str:
        return "A" if score >= 85 else "B" if score >= 75 else "C" if score >= 65 else "D" if score >= 50 else "F"

    def _severity(self, profile: WalkForwardProfile) -> str:
        if profile.worst_oos_drawdown_pct > self.policy.maximum_oos_drawdown_pct:
            return "CRITICAL"
        if profile.average_degradation_pct > self.policy.maximum_degradation_pct:
            return "SEVERE"
        if profile.parameter_stability_score < 50.0:
            return "MODERATE"
        return "LOW"

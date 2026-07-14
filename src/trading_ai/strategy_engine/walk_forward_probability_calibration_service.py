from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np

from trading_ai.strategy_engine.probability_calibration_model_registry import (
    ProbabilityCalibrationModelRegistry,
)
from trading_ai.strategy_engine.walk_forward_policy import WalkForwardPolicy
from trading_ai.strategy_engine.walk_forward_splitter import InstitutionalWalkForwardSplitter
from trading_ai.strategy_engine.walk_forward_probability_calibration_adapter import (
    WalkForwardProbabilityCalibrationAdapter,
)
from trading_ai.strategy_engine.walk_forward_probability_calibration_policy import (
    WalkForwardProbabilityCalibrationPolicy,
)
from trading_ai.strategy_engine.walk_forward_probability_calibration_profile import (
    WalkForwardCalibrationWindowResult,
    WalkForwardProbabilityCalibrationProfile,
)


class WalkForwardProbabilityCalibrationService:
    """Leakage-aware rolling retraining and out-of-sample calibration validation."""

    def __init__(
        self,
        walk_forward_policy: WalkForwardPolicy | None = None,
        calibration_walk_forward_policy: WalkForwardProbabilityCalibrationPolicy | None = None,
        adapter: WalkForwardProbabilityCalibrationAdapter | None = None,
        registry: ProbabilityCalibrationModelRegistry | None = None,
    ) -> None:
        self.walk_forward_policy = walk_forward_policy or WalkForwardPolicy()
        self.policy = calibration_walk_forward_policy or WalkForwardProbabilityCalibrationPolicy()
        self.policy.validate()
        self.splitter = InstitutionalWalkForwardSplitter(self.walk_forward_policy)
        self.adapter = adapter or WalkForwardProbabilityCalibrationAdapter()
        self.registry = registry

    def run(
        self,
        observations: Sequence[Any],
        parameter_grid: Iterable[dict[str, Any]],
        *,
        version_prefix: str = "wf-cal",
    ) -> WalkForwardProbabilityCalibrationProfile:
        windows = self.splitter.split(len(observations))
        profile = WalkForwardProbabilityCalibrationProfile(
            window_count=len(windows),
            metadata={"version_prefix": version_prefix},
        )
        parameters = [dict(item) for item in parameter_grid]
        if not parameters:
            profile.rejection_reasons.append("EMPTY_CALIBRATION_PARAMETER_GRID")
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

            evaluated = []
            for params in parameters:
                try:
                    model = self.adapter.train(train, params)
                    validation_metrics = self.adapter.evaluate(model, validation)
                    score = self.adapter.objective(validation_metrics, self.policy.objective_weights)
                    evaluated.append((score, params, model, validation_metrics))
                except Exception as exc:
                    profile.warnings.append(
                        f"CALIBRATION_PARAMETER_EVALUATION_FAILED:{type(exc).__name__}"
                    )
            if not evaluated:
                continue
            evaluated.sort(key=lambda item: (item[0], str(sorted(item[1].items()))), reverse=True)
            _, selected_parameters, selected_model, validation_metrics = evaluated[0]

            production_training = list(train)
            if self.policy.retrain_on_train_and_validation:
                production_training.extend(validation)
                selected_model = self.adapter.train(production_training, selected_parameters)
            test_metrics = self.adapter.evaluate(selected_model, test)
            model_version = "UNAVAILABLE"
            if self.policy.register_window_models and self.registry is not None:
                model_version = f"{version_prefix}-{window.window_id.lower()}"
                self.registry.register(
                    selected_model,
                    version=model_version,
                    activate=False,
                    metadata={
                        "walk_forward_window_id": window.window_id,
                        "selected_parameters": selected_parameters,
                    },
                )

            degradation = max(
                0.0,
                (validation_metrics.model_score - test_metrics.model_score)
                / max(abs(validation_metrics.model_score), 1e-12),
            )
            result = WalkForwardCalibrationWindowResult(
                window_id=window.window_id,
                selected_parameters=selected_parameters,
                validation_metrics=validation_metrics,
                test_metrics=test_metrics,
                model_registry_id=str(getattr(selected_model, "registry_id", "UNAVAILABLE")),
                model_version=model_version,
                model_segment_count=int(getattr(selected_model, "segment_count", 0)),
                model_valid_segment_count=int(getattr(selected_model, "valid_segment_count", 0)),
                model_score_degradation=degradation,
                metadata={
                    "train_start": window.train_start,
                    "train_end": window.train_end,
                    "validation_start": window.validation_start,
                    "validation_end": window.validation_end,
                    "test_start": window.test_start,
                    "test_end": window.test_end,
                },
            )
            self._enforce(result)
            profile.results.append(result)

        self._finalize(profile)
        if (
            profile.valid
            and self.policy.activate_latest_model
            and self.registry is not None
            and profile.results
        ):
            registered = [item for item in profile.results if item.model_version != "UNAVAILABLE"]
            if registered:
                active = self.registry.activate(registered[-1].model_version)
                profile.active_model_version = active.version
        return profile

    def _enforce(self, result: WalkForwardCalibrationWindowResult) -> None:
        metrics = result.test_metrics
        if not metrics.valid:
            result.valid = False
            result.allowed = False
            result.rejection_reasons.append("INVALID_OOS_CALIBRATION_METRICS")
            return
        if metrics.brier_improvement < self.policy.minimum_oos_brier_improvement:
            result.allowed = False
            result.rejection_reasons.append("OOS_BRIER_IMPROVEMENT_BELOW_MINIMUM")
        if metrics.log_loss_improvement < self.policy.minimum_oos_log_loss_improvement:
            result.allowed = False
            result.rejection_reasons.append("OOS_LOG_LOSS_IMPROVEMENT_BELOW_MINIMUM")
        if metrics.expected_calibration_error > self.policy.maximum_oos_ece:
            result.allowed = False
            result.rejection_reasons.append("OOS_ECE_LIMIT_EXCEEDED")
        if metrics.maximum_calibration_error > self.policy.maximum_oos_mce:
            result.warnings.append("OOS_MCE_ELEVATED")
        if metrics.segment_coverage < self.policy.minimum_segment_coverage:
            result.warnings.append("SEGMENT_COVERAGE_BELOW_TARGET")
        if result.model_score_degradation > self.policy.maximum_model_score_degradation:
            result.warnings.append("CALIBRATION_MODEL_SCORE_DEGRADATION")
        if self.policy.reject_critical_calibration and str(metrics.metadata.get("severity", "")).upper() == "CRITICAL":
            result.allowed = False
            result.rejection_reasons.append("CRITICAL_OOS_CALIBRATION_RISK")

    def _finalize(self, profile: WalkForwardProbabilityCalibrationProfile) -> None:
        results = profile.results
        profile.completed_window_count = len(results)
        if len(results) < self.policy.minimum_completed_windows:
            profile.rejection_reasons.append("INSUFFICIENT_COMPLETED_CALIBRATION_WINDOWS")
            profile.risk_severity = "CRITICAL"
            return
        test = [item.test_metrics for item in results]
        profile.average_oos_brier_improvement = float(np.mean([x.brier_improvement for x in test]))
        profile.average_oos_log_loss_improvement = float(np.mean([x.log_loss_improvement for x in test]))
        profile.average_oos_ece = float(np.mean([x.expected_calibration_error for x in test]))
        profile.worst_oos_mce = max(x.maximum_calibration_error for x in test)
        profile.average_segment_coverage = float(np.mean([x.segment_coverage for x in test]))
        profile.average_model_score = float(np.mean([x.model_score for x in test]))
        signatures = [tuple(sorted(item.selected_parameters.items())) for item in results]
        dominant = Counter(signatures).most_common(1)[0][1]
        profile.model_stability_score = 100.0 * dominant / len(signatures)
        profile.calibration_walk_forward_score = self._score(profile)
        profile.calibration_walk_forward_grade = self._grade(profile.calibration_walk_forward_score)
        profile.risk_severity = self._severity(profile)
        profile.valid = True
        profile.allowed = all(item.allowed for item in results)
        if not profile.allowed:
            profile.rejection_reasons.append("ONE_OR_MORE_CALIBRATION_WINDOWS_REJECTED")

    def _score(self, profile: WalkForwardProbabilityCalibrationProfile) -> float:
        brier = min(100.0, max(0.0, 50.0 + 200.0 * profile.average_oos_brier_improvement))
        log_loss = min(100.0, max(0.0, 50.0 + 200.0 * profile.average_oos_log_loss_improvement))
        ece = 100.0 * (1.0 - min(profile.average_oos_ece / max(self.policy.maximum_oos_ece, 1e-12), 1.0))
        coverage = 100.0 * profile.average_segment_coverage
        score = 0.30 * brier + 0.20 * log_loss + 0.20 * ece + 0.10 * coverage + 0.10 * profile.average_model_score + 0.10 * profile.model_stability_score
        return round(min(100.0, max(0.0, score)), 2)

    @staticmethod
    def _grade(score: float) -> str:
        return "A" if score >= 85 else "B" if score >= 75 else "C" if score >= 65 else "D" if score >= 50 else "F"

    def _severity(self, profile: WalkForwardProbabilityCalibrationProfile) -> str:
        if profile.average_oos_ece > self.policy.maximum_oos_ece or profile.worst_oos_mce > self.policy.maximum_oos_mce * 1.5:
            return "CRITICAL"
        if profile.average_oos_brier_improvement < 0 or profile.average_oos_log_loss_improvement < 0:
            return "SEVERE"
        if profile.model_stability_score < 50.0 or profile.average_segment_coverage < self.policy.minimum_segment_coverage:
            return "MODERATE"
        return "LOW"

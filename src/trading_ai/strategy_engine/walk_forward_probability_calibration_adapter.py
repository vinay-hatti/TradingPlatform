from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

import numpy as np

from trading_ai.strategy_engine.probability_calibration_dataset_builder import (
    ProbabilityCalibrationDatasetBuilder,
)
from trading_ai.strategy_engine.probability_calibration_policy import (
    ProbabilityCalibrationPolicy,
)
from trading_ai.strategy_engine.segmented_probability_calibration_engine import (
    SegmentedProbabilityCalibrationEngine,
)
from trading_ai.strategy_engine.segmented_probability_calibration_policy import (
    SegmentedProbabilityCalibrationPolicy,
)
from trading_ai.strategy_engine.segmented_probability_calibration_service import (
    SegmentedProbabilityCalibrationService,
)
from trading_ai.strategy_engine.walk_forward_probability_calibration_profile import (
    WalkForwardCalibrationMetrics,
)


class WalkForwardProbabilityCalibrationAdapter:
    """Fits Phase 6 calibration models and evaluates them on untouched records."""

    def __init__(self, dataset_builder: ProbabilityCalibrationDatasetBuilder | None = None) -> None:
        self.dataset_builder = dataset_builder or ProbabilityCalibrationDatasetBuilder()

    def train(self, records: Sequence[Any], parameters: dict[str, Any]):
        calibration_policy, segment_policy = self._policies(parameters)
        engine = SegmentedProbabilityCalibrationEngine(
            calibration_policy=calibration_policy,
            segment_policy=segment_policy,
        )
        service = SegmentedProbabilityCalibrationService(
            dataset_builder=self.dataset_builder,
            engine=engine,
        )
        return service.train(records)

    def evaluate(self, model, records: Sequence[Any]) -> WalkForwardCalibrationMetrics:
        dataset = self.dataset_builder.build(records)
        if not dataset.valid:
            return WalkForwardCalibrationMetrics(
                observation_count=dataset.accepted_count,
                valid=False,
                rejection_reasons=["EMPTY_CALIBRATION_EVALUATION_DATASET"],
            )

        raw = np.asarray(dataset.probabilities, dtype=float)
        outcomes = np.asarray(dataset.outcomes, dtype=float)
        calibrated = []
        segmented = model is not None and getattr(model, "valid", False)
        engine = SegmentedProbabilityCalibrationEngine()
        covered = 0
        selected_segments: dict[str, int] = {}
        for probability, observation in zip(raw, dataset.observations):
            profile, segment_key = engine.select_profile(
                model,
                symbol=observation.symbol,
                strategy=observation.strategy,
                direction=observation.direction,
                market_regime=observation.market_regime,
            ) if segmented else (None, "UNAVAILABLE")
            if profile is None:
                calibrated.append(float(probability))
            else:
                value = engine.calibration_engine.calibrate(profile, float(probability))
                calibrated.append(float(value))
                covered += 1
                selected_segments[segment_key] = selected_segments.get(segment_key, 0) + 1

        calibrated_array = np.asarray(calibrated, dtype=float)
        raw_brier = float(np.mean((raw - outcomes) ** 2))
        calibrated_brier = float(np.mean((calibrated_array - outcomes) ** 2))
        raw_log = self._log_loss(raw, outcomes)
        calibrated_log = self._log_loss(calibrated_array, outcomes)
        ece, mce = self._calibration_errors(calibrated_array, outcomes)
        return WalkForwardCalibrationMetrics(
            observation_count=len(outcomes),
            raw_brier_score=raw_brier,
            calibrated_brier_score=calibrated_brier,
            raw_log_loss=raw_log,
            calibrated_log_loss=calibrated_log,
            brier_improvement=self._relative_improvement(raw_brier, calibrated_brier),
            log_loss_improvement=self._relative_improvement(raw_log, calibrated_log),
            expected_calibration_error=ece,
            maximum_calibration_error=mce,
            segment_coverage=covered / len(outcomes) if len(outcomes) else 0.0,
            model_score=float(getattr(model, "calibration_score", 0.0)),
            valid=True,
            metadata={
                "selected_segments": selected_segments,
                "dataset_rejections": dataset.rejection_counts,
            },
        )

    @staticmethod
    def objective(metrics: WalkForwardCalibrationMetrics, weights: dict[str, float]) -> float:
        if not metrics.valid:
            return -1.0
        brier = 50.0 + 100.0 * metrics.brier_improvement
        log_loss = 50.0 + 100.0 * metrics.log_loss_improvement
        ece = 100.0 * (1.0 - min(max(metrics.expected_calibration_error, 0.0), 1.0))
        coverage = 100.0 * metrics.segment_coverage
        score = (
            weights.get("brier", 0.35) * brier
            + weights.get("log_loss", 0.25) * log_loss
            + weights.get("ece", 0.20) * ece
            + weights.get("coverage", 0.10) * coverage
            + weights.get("model_score", 0.10) * metrics.model_score
        )
        return round(min(100.0, max(0.0, score)), 4)

    @staticmethod
    def _relative_improvement(raw: float, calibrated: float) -> float:
        return (raw - calibrated) / max(abs(raw), 1e-12)

    @staticmethod
    def _log_loss(probabilities: np.ndarray, outcomes: np.ndarray) -> float:
        clipped = np.clip(probabilities, 1e-9, 1.0 - 1e-9)
        return float(-np.mean(outcomes * np.log(clipped) + (1.0 - outcomes) * np.log(1.0 - clipped)))

    @staticmethod
    def _calibration_errors(probabilities: np.ndarray, outcomes: np.ndarray, bins: int = 10):
        edges = np.linspace(0.0, 1.0, bins + 1)
        total = len(probabilities)
        ece = 0.0
        mce = 0.0
        for index in range(bins):
            if index == bins - 1:
                mask = (probabilities >= edges[index]) & (probabilities <= edges[index + 1])
            else:
                mask = (probabilities >= edges[index]) & (probabilities < edges[index + 1])
            count = int(mask.sum())
            if not count:
                continue
            gap = abs(float(probabilities[mask].mean()) - float(outcomes[mask].mean()))
            ece += count / max(total, 1) * gap
            mce = max(mce, gap)
        return float(ece), float(mce)

    @staticmethod
    def _policies(parameters: dict[str, Any]):
        calibration_fields = set(ProbabilityCalibrationPolicy.__dataclass_fields__)
        segment_fields = set(SegmentedProbabilityCalibrationPolicy.__dataclass_fields__)
        calibration_kwargs = {k: v for k, v in parameters.items() if k in calibration_fields}
        segment_kwargs = {k: v for k, v in parameters.items() if k in segment_fields}
        unsupported = set(parameters) - calibration_fields - segment_fields
        if unsupported:
            raise ValueError(f"unsupported calibration policy fields: {sorted(unsupported)}")
        calibration_policy = ProbabilityCalibrationPolicy(**calibration_kwargs)
        segment_policy = SegmentedProbabilityCalibrationPolicy(**segment_kwargs)
        segment_policy.validate()
        return calibration_policy, segment_policy

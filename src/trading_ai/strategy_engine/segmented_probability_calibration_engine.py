from __future__ import annotations

import hashlib
from collections import defaultdict
from itertools import combinations

from trading_ai.strategy_engine.probability_calibration_dataset_profile import ProbabilityCalibrationDataset
from trading_ai.strategy_engine.probability_calibration_engine import ProbabilityCalibrationEngine
from trading_ai.strategy_engine.probability_calibration_policy import ProbabilityCalibrationPolicy
from trading_ai.strategy_engine.segmented_probability_calibration_policy import SegmentedProbabilityCalibrationPolicy
from trading_ai.strategy_engine.segmented_probability_calibration_profile import (
    SegmentCalibrationResult, SegmentedProbabilityCalibrationProfile,
)


class SegmentedProbabilityCalibrationEngine:
    def __init__(self, calibration_policy: ProbabilityCalibrationPolicy | None = None,
                 segment_policy: SegmentedProbabilityCalibrationPolicy | None = None,
                 calibration_engine: ProbabilityCalibrationEngine | None = None):
        self.calibration_policy = calibration_policy or ProbabilityCalibrationPolicy()
        self.segment_policy = segment_policy or SegmentedProbabilityCalibrationPolicy()
        self.segment_policy.validate()
        self.calibration_engine = calibration_engine or ProbabilityCalibrationEngine(self.calibration_policy)

    def analyze(self, dataset: ProbabilityCalibrationDataset) -> SegmentedProbabilityCalibrationProfile:
        if not dataset.valid:
            return self._invalid("EMPTY_CALIBRATION_DATASET", dataset.accepted_count)
        observations = dataset.observations
        global_profile = None
        if self.segment_policy.train_global_model:
            global_profile = self._fit(observations, "GLOBAL", "PORTFOLIO", "ALL")

        segment_results = {}
        priority = 0
        dimensions = self.segment_policy.segment_dimensions
        for depth in range(1, self.segment_policy.maximum_segment_depth + 1):
            for combo in combinations(dimensions, depth):
                buckets = defaultdict(list)
                for item in observations:
                    key_values = tuple(getattr(item, name) for name in combo)
                    buckets[key_values].append(item)
                for values, items in sorted(buckets.items()):
                    positives = sum(x.outcome for x in items)
                    negatives = len(items) - positives
                    if len(items) < self.segment_policy.minimum_segment_observations:
                        continue
                    if positives < self.segment_policy.minimum_segment_positive_observations:
                        continue
                    if negatives < self.segment_policy.minimum_segment_negative_observations:
                        continue
                    dim_map = dict(zip(combo, values))
                    key = self.segment_key(dim_map)
                    strategy = dim_map.get("strategy", "ALL")
                    symbol = dim_map.get("symbol", "PORTFOLIO")
                    profile = self._fit(items, key, symbol, strategy)
                    priority += 1
                    segment_results[key] = SegmentCalibrationResult(
                        segment_key=key, dimensions=dim_map,
                        observation_count=len(items), profile=profile, priority=priority,
                    )

        valid_profiles = [x.profile for x in segment_results.values() if x.profile.valid]
        if global_profile and global_profile.valid:
            valid_profiles.append(global_profile)
        valid = bool(valid_profiles)
        allowed_profiles = [x for x in valid_profiles if x.allowed]
        allowed = bool(allowed_profiles) if self.segment_policy.require_allowed_segment_model else valid
        score = sum(x.calibration_score * x.observation_count for x in valid_profiles) / max(
            sum(x.observation_count for x in valid_profiles), 1
        ) if valid_profiles else 0.0
        severity = self._worst_severity([x.calibration_severity for x in valid_profiles])
        warnings = []
        rejections = []
        if not segment_results:
            warnings.append("NO_SEGMENTS_MET_MINIMUM_SAMPLE_REQUIREMENTS")
        if not valid:
            rejections.append("NO_VALID_CALIBRATION_MODEL")
        if valid and not allowed:
            rejections.append("NO_ALLOWED_CALIBRATION_MODEL")
        registry_id = hashlib.sha256(
            f"{dataset.accepted_count}|{sorted(segment_results)}|{getattr(global_profile, 'model_id', '')}".encode()
        ).hexdigest()[:16]
        return SegmentedProbabilityCalibrationProfile(
            registry_id=f"CALREG-{registry_id}", global_profile=global_profile,
            segment_profiles=segment_results, segment_count=len(segment_results),
            valid_segment_count=sum(1 for x in segment_results.values() if x.profile.valid),
            observation_count=dataset.accepted_count, calibration_score=score,
            calibration_grade=self._grade(score), calibration_severity=severity,
            allowed=allowed, valid=valid, warnings=warnings,
            rejection_reasons=rejections,
            metadata={"dataset_rejections": dataset.rejection_counts},
        )

    def select_profile(self, registry: SegmentedProbabilityCalibrationProfile, **context):
        candidates = []
        for result in registry.segment_profiles.values():
            if all(str(context.get(k, "UNKNOWN")).upper() == str(v).upper() for k, v in result.dimensions.items()):
                candidates.append(result)
        candidates.sort(key=lambda x: (len(x.dimensions), x.observation_count, x.profile.calibration_score), reverse=True)
        for candidate in candidates:
            if candidate.profile.valid and (candidate.profile.allowed or not self.segment_policy.require_allowed_segment_model):
                return candidate.profile, candidate.segment_key
        if registry.global_profile and registry.global_profile.valid:
            return registry.global_profile, "GLOBAL"
        return None, "UNAVAILABLE"

    @staticmethod
    def segment_key(dimensions):
        if not dimensions:
            return "GLOBAL"
        return "|".join(f"{key.upper()}={str(value).upper()}" for key, value in sorted(dimensions.items()))

    def _fit(self, observations, segment, symbol, strategy):
        return self.calibration_engine.analyze(
            [x.probability for x in observations], [x.outcome for x in observations],
            sample_weights=[x.sample_weight for x in observations],
            timestamps=[x.timestamp for x in observations], symbol=symbol,
            strategy=strategy, segment=segment,
        )

    def _invalid(self, reason, count):
        return SegmentedProbabilityCalibrationProfile(
            registry_id="CALREG-INVALID", global_profile=None, observation_count=count,
            valid=False, allowed=False, rejection_reasons=[reason],
        )

    @staticmethod
    def _grade(score):
        return "A" if score >= 85 else "B" if score >= 75 else "C" if score >= 65 else "D" if score >= 50 else "F"

    @staticmethod
    def _worst_severity(values):
        order = {"UNKNOWN": 0, "LOW": 1, "MODERATE": 2, "SEVERE": 3, "CRITICAL": 4}
        return max(values or ["UNKNOWN"], key=lambda x: order.get(str(x).upper(), 0))

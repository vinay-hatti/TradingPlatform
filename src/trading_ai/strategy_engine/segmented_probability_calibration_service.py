from trading_ai.strategy_engine.probability_calibration_dataset_builder import ProbabilityCalibrationDatasetBuilder
from trading_ai.strategy_engine.segmented_probability_calibration_engine import SegmentedProbabilityCalibrationEngine


class SegmentedProbabilityCalibrationService:
    def __init__(self, dataset_builder=None, engine=None, registry=None):
        self.dataset_builder = dataset_builder or ProbabilityCalibrationDatasetBuilder()
        self.engine = engine or SegmentedProbabilityCalibrationEngine()
        self.registry = registry

    def train(self, records, *, register=False, version=None, metadata=None):
        dataset = self.dataset_builder.build(records)
        profile = self.engine.analyze(dataset)
        if register:
            if self.registry is None:
                raise ValueError("registry is required when register=True")
            self.registry.register(profile, version=version, metadata=metadata)
        return profile

    def calibrate(self, registry_profile, probability: float, **context):
        profile, segment_key = self.engine.select_profile(registry_profile, **context)
        if profile is None:
            return min(max(float(probability), 0.0), 1.0), "UNAVAILABLE"
        calibrated = self.engine.calibration_engine.calibrate(profile, probability)
        return calibrated, segment_key

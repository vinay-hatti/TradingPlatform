from trading_ai.strategy_engine.probability_calibration_drift_engine import ProbabilityCalibrationDriftEngine
class ProbabilityCalibrationDriftService:
    def __init__(self, policy=None, engine=None): self.engine=engine or ProbabilityCalibrationDriftEngine(policy)
    def analyze(self, *args, **kwargs): return self.engine.analyze(*args, **kwargs)

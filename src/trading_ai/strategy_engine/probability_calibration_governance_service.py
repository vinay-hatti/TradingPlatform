from trading_ai.strategy_engine.probability_calibration_governance_engine import ProbabilityCalibrationGovernanceEngine
class ProbabilityCalibrationGovernanceService:
    def __init__(self, policy=None, engine=None, registry=None): self.engine=engine or ProbabilityCalibrationGovernanceEngine(policy); self.registry=registry
    def evaluate(self,*args,**kwargs): return self.engine.evaluate(*args,**kwargs)
    def evaluate_and_promote(self, champion_profile, challenger_profile, probabilities, outcomes, *, champion_version, challenger_version, drift_profile=None, apply_promotion=None):
        result=self.engine.evaluate(champion_profile,challenger_profile,probabilities,outcomes,champion_version=champion_version,challenger_version=challenger_version,drift_profile=drift_profile)
        enabled=self.engine.policy.automatic_promotion_enabled if apply_promotion is None else bool(apply_promotion)
        if enabled and result.promotion_eligible and self.registry is not None:
            self.registry.activate(challenger_version); result.promotion_applied=True
        return result

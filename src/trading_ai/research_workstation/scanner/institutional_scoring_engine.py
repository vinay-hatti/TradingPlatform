from .institutional_scanner_policy import InstitutionalScannerScoringPolicy
from .institutional_scanner_profile import InstitutionalScannerDecisionProfile
class InstitutionalScannerScoringEngine:
    def __init__(self,policy=None): self.policy=policy or InstitutionalScannerScoringPolicy(); self.policy.validate()
    @staticmethod
    def _b(v): return max(0.0,min(100.0,float(v)))
    def score(self,p:InstitutionalScannerDecisionProfile)->float:
        x=self.policy
        value=self._b(p.calibrated_probability*100)*x.probability_weight+self._b(p.expected_return*100)*x.expected_return_weight+self._b(p.reward_risk_ratio*25)*x.reward_risk_weight+self._b(p.regime_confidence)*x.regime_confidence_weight+self._b(p.execution_quality)*x.execution_quality_weight+self._b(100-p.tail_risk_score)*x.tail_risk_weight
        return round(value,6)

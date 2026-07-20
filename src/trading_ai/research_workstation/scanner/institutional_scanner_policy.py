from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class InstitutionalScannerScoringPolicy:
    probability_weight: float = 0.35
    expected_return_weight: float = 0.20
    reward_risk_weight: float = 0.15
    regime_confidence_weight: float = 0.15
    execution_quality_weight: float = 0.10
    tail_risk_weight: float = 0.05
    def validate(self) -> None:
        values=(self.probability_weight,self.expected_return_weight,self.reward_risk_weight,self.regime_confidence_weight,self.execution_quality_weight,self.tail_risk_weight)
        if any(v<0 for v in values): raise ValueError('Institutional scoring weights cannot be negative.')
        if abs(sum(values)-1.0)>1e-9: raise ValueError('Institutional scoring weights must sum to 1.0.')

@dataclass(frozen=True)
class InstitutionalScannerFilterPolicy:
    minimum_probability_of_profit: float = 0.0
    minimum_expected_return: float = -100.0
    minimum_reward_risk_ratio: float = 0.0
    minimum_decision_confidence: float = 0.0
    require_allowed: bool = False
    require_selected: bool = False

from dataclasses import dataclass


@dataclass(frozen=True)
class CrossAssetIntelligencePolicy:
    intermarket_weight: float = 0.45
    sector_weight: float = 0.30
    structure_weight: float = 0.25

    risk_on_threshold: float = 0.20
    risk_off_threshold: float = -0.20

    minimum_confidence_ready: float = 0.35
    minimum_confidence_review: float = 0.15

    maximum_call_adjustment: float = 0.20
    maximum_put_adjustment: float = 0.20

    high_systemic_risk_position_multiplier: float = 0.50
    elevated_systemic_risk_position_multiplier: float = 0.75
    normal_position_multiplier: float = 1.00

    high_confidence_multiplier: float = 1.10
    low_confidence_multiplier: float = 0.85

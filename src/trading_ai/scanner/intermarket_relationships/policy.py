from dataclasses import dataclass


@dataclass(frozen=True)
class IntermarketRelationshipPolicy:
    minimum_required_relationships_ready: int = 7
    minimum_required_relationships_review: int = 4

    positive_signal_weight: float = 1.0
    strong_signal_weight: float = 1.5

    equity_positive_threshold: float = 0.0
    relative_strength_threshold: float = 0.0
    volatility_risk_off_threshold: float = 0.05
    credit_risk_on_threshold: float = 0.0
    dollar_headwind_threshold: float = 0.03

    risk_on_state_threshold: float = 0.20
    risk_off_state_threshold: float = -0.20

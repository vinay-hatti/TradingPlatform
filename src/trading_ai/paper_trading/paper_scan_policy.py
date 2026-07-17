from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PaperScanAutomationPolicy:
    maximum_candidates_per_cycle: int = 100
    maximum_approved_candidates_per_cycle: int = 20
    maximum_orders_created_per_cycle: int = 20
    minimum_candidate_score: float = 70.0
    minimum_decision_probability: float = 0.55
    require_decision_approval: bool = True
    require_risk_gateway_approval: bool = True
    reject_duplicate_symbol_strategy: bool = True
    reject_missing_market_price: bool = True
    reject_missing_expiration_for_options: bool = True
    reject_missing_strike_for_options: bool = True
    default_option_multiplier: int = 100
    default_equity_multiplier: int = 1
    fail_closed: bool = True

    def validate(self) -> None:
        for name in (
            "maximum_candidates_per_cycle",
            "maximum_approved_candidates_per_cycle",
            "maximum_orders_created_per_cycle",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if not 0 <= self.minimum_candidate_score <= 100:
            raise ValueError("minimum_candidate_score must be between 0 and 100")
        if not 0 <= self.minimum_decision_probability <= 1:
            raise ValueError("minimum_decision_probability must be between 0 and 1")

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PreTradeGovernancePolicy:
    minimum_trade_construction_score: float = 70.0
    minimum_portfolio_health_score: float = 60.0
    minimum_lifecycle_score: float = 70.0
    minimum_probability_of_profit: float = 0.50
    minimum_reward_risk_ratio: float = 1.0
    maximum_position_risk_pct: float = 0.05
    maximum_portfolio_risk_pct: float = 0.15
    maximum_buying_power_pct: float = 0.65
    maximum_abs_portfolio_delta: float = 5000.0
    maximum_abs_portfolio_gamma: float = 1000.0
    maximum_abs_portfolio_vega: float = 5000.0
    maximum_bid_ask_spread_pct: float = 0.25
    minimum_open_interest: int = 100
    minimum_option_volume: int = 25
    require_defined_risk: bool = True
    require_lifecycle_ready: bool = True
    require_broker_ready: bool = True
    require_compliance_clearance: bool = True
    manager_approval_risk_pct: float = 0.04
    risk_committee_risk_pct: float = 0.10
    auto_approval_minimum_score: float = 90.0
    warning_approval_minimum_score: float = 80.0
    manager_approval_minimum_score: float = 70.0
    maximum_warning_count_for_auto_approval: int = 0
    maximum_warning_count_for_warning_approval: int = 3

    def validate(self) -> None:
        percentage_fields = (
            "maximum_position_risk_pct",
            "maximum_portfolio_risk_pct",
            "maximum_buying_power_pct",
            "manager_approval_risk_pct",
            "risk_committee_risk_pct",
        )
        for name in percentage_fields:
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1.")

        score_fields = (
            "minimum_trade_construction_score",
            "minimum_portfolio_health_score",
            "minimum_lifecycle_score",
            "auto_approval_minimum_score",
            "warning_approval_minimum_score",
            "manager_approval_minimum_score",
        )
        for name in score_fields:
            value = float(getattr(self, name))
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be between 0 and 100.")

        if not 0.0 <= self.minimum_probability_of_profit <= 1.0:
            raise ValueError(
                "minimum_probability_of_profit must be between 0 and 1."
            )
        if self.minimum_reward_risk_ratio < 0:
            raise ValueError(
                "minimum_reward_risk_ratio cannot be negative."
            )
        if self.manager_approval_risk_pct > self.risk_committee_risk_pct:
            raise ValueError(
                "Manager approval threshold cannot exceed committee threshold."
            )
        if self.maximum_warning_count_for_auto_approval < 0:
            raise ValueError("Warning count cannot be negative.")
        if self.maximum_warning_count_for_warning_approval < 0:
            raise ValueError("Warning count cannot be negative.")

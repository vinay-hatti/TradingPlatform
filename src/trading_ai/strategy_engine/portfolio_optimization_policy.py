from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioOptimizationPolicy:
    """Institutional portfolio-optimization limits and objective weights."""

    maximum_portfolio_exposure_pct: float = 0.50
    maximum_total_risk_pct: float = 0.20
    reserve_cash_pct: float = 0.20
    maximum_position_weight_pct: float = 0.12
    maximum_sector_weight_pct: float = 0.30
    maximum_strategy_weight_pct: float = 0.35
    maximum_correlation_group_weight_pct: float = 0.25
    maximum_positions: int = 10

    maximum_absolute_delta: float = 500.0
    maximum_absolute_gamma: float = 25.0
    maximum_absolute_theta: float = 1000.0
    maximum_absolute_vega: float = 2500.0
    maximum_absolute_rho: float = 2500.0

    minimum_candidate_score: float = 45.0
    minimum_surface_score: float = 35.0
    minimum_allocation_dollars: float = 100.0
    allocation_step_pct: float = 0.01

    expected_return_weight: float = 0.30
    ranking_score_weight: float = 0.20
    strategy_score_weight: float = 0.10
    surface_score_weight: float = 0.15
    diversification_weight: float = 0.15
    capital_efficiency_weight: float = 0.10

    tail_risk_penalty_weight: float = 0.20
    concentration_penalty_weight: float = 0.15
    greek_penalty_weight: float = 0.10

    reject_critical_surface_risk: bool = True
    reject_disallowed_candidates: bool = True

    def validate(self) -> None:
        pct_fields = {
            "maximum_portfolio_exposure_pct": self.maximum_portfolio_exposure_pct,
            "maximum_total_risk_pct": self.maximum_total_risk_pct,
            "reserve_cash_pct": self.reserve_cash_pct,
            "maximum_position_weight_pct": self.maximum_position_weight_pct,
            "maximum_sector_weight_pct": self.maximum_sector_weight_pct,
            "maximum_strategy_weight_pct": self.maximum_strategy_weight_pct,
            "maximum_correlation_group_weight_pct": self.maximum_correlation_group_weight_pct,
            "allocation_step_pct": self.allocation_step_pct,
        }
        for name, value in pct_fields.items():
            if value < 0.0 or value > 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.maximum_portfolio_exposure_pct + self.reserve_cash_pct > 1.0:
            raise ValueError("portfolio exposure plus reserve cash cannot exceed 100%")
        if self.maximum_positions <= 0:
            raise ValueError("maximum_positions must be greater than zero")
        if self.minimum_allocation_dollars < 0.0:
            raise ValueError("minimum_allocation_dollars cannot be negative")
        objective_weight = (
            self.expected_return_weight
            + self.ranking_score_weight
            + self.strategy_score_weight
            + self.surface_score_weight
            + self.diversification_weight
            + self.capital_efficiency_weight
        )
        if objective_weight <= 0.0:
            raise ValueError("at least one objective weight must be positive")

from dataclasses import dataclass, field


@dataclass
class PortfolioOptimizationFrontierPoint:
    point_id: str
    maximum_exposure_pct: float
    maximum_risk_pct: float
    maximum_concentration_pct: float
    selected_count: int
    allocated_capital: float
    exposure_pct: float
    maximum_loss: float
    risk_pct: float
    expected_profit: float
    expected_return_pct: float
    objective_score: float
    diversification_score: float
    concentration_score: float
    greek_utilization_score: float
    optimization_grade: str
    risk_severity: str
    allowed: bool
    valid: bool
    pareto_efficient: bool = False
    allocation_ids: list[str] = field(default_factory=list)
    allocation_weights: dict[str, float] = field(default_factory=dict)
    binding_constraints: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class PortfolioOptimizationFrontierProfile:
    initial_capital: float
    candidate_count: int
    point_count: int
    valid_point_count: int
    pareto_point_count: int
    best_point_id: str | None
    best_objective_score: float
    best_expected_return_pct: float
    lowest_risk_pct: float
    highest_expected_return_pct: float
    objective_range: float
    expected_return_range: float
    risk_range: float
    selection_stability_score: float
    allocation_stability_score: float
    constraint_sensitivity_score: float
    frontier_score: float
    frontier_grade: str
    risk_severity: str
    allowed: bool
    valid: bool
    points: list[PortfolioOptimizationFrontierPoint] = field(default_factory=list)
    pareto_points: list[PortfolioOptimizationFrontierPoint] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

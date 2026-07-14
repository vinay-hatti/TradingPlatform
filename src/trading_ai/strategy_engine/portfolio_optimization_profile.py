from dataclasses import dataclass, field
from typing import Any


@dataclass
class PortfolioOptimizationCandidate:
    candidate_id: str
    symbol: str
    strategy: str
    sector: str
    correlation_group: str
    capital_required: float
    maximum_loss: float
    expected_profit: float
    expected_return_pct: float
    ranking_score: float
    strategy_score: float
    surface_score: float
    surface_severity: str
    allowed: bool
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    metadata: dict = field(default_factory=dict)
    source: Any = None


@dataclass
class PortfolioOptimizationAllocation:
    candidate_id: str
    symbol: str
    strategy: str
    allocation_dollars: float
    allocation_weight_pct: float
    allocation_multiplier: float
    expected_profit: float
    maximum_loss: float
    expected_return_pct: float
    marginal_objective_score: float
    ranking_score: float
    surface_score: float
    sector: str
    correlation_group: str
    metadata: dict = field(default_factory=dict)


@dataclass
class PortfolioOptimizationProfile:
    initial_capital: float
    candidate_count: int
    selected_count: int
    total_allocated_capital: float
    portfolio_exposure_pct: float
    reserve_cash: float
    reserve_cash_pct: float
    total_maximum_loss: float
    total_risk_pct: float
    expected_portfolio_profit: float
    expected_portfolio_return_pct: float
    weighted_ranking_score: float
    weighted_strategy_score: float
    weighted_surface_score: float
    diversification_score: float
    capital_efficiency_score: float
    concentration_score: float
    greek_utilization_score: float
    objective_score: float
    optimization_grade: str
    risk_severity: str
    allowed: bool
    valid: bool
    allocations: list[PortfolioOptimizationAllocation] = field(default_factory=list)
    rejected_candidates: list[dict] = field(default_factory=list)
    sector_weights: list[dict] = field(default_factory=list)
    strategy_weights: list[dict] = field(default_factory=list)
    correlation_group_weights: list[dict] = field(default_factory=list)
    greek_totals: dict = field(default_factory=dict)
    binding_constraints: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

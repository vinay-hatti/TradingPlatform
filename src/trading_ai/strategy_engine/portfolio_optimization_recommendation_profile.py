from dataclasses import dataclass, field
from typing import Any


@dataclass
class PortfolioOptimizationPolicyRecommendation:
    source_point_id: str | None
    maximum_portfolio_exposure_pct: float
    maximum_total_risk_pct: float
    maximum_sector_weight_pct: float
    maximum_strategy_weight_pct: float
    maximum_correlation_group_weight_pct: float
    expected_return_pct: float
    objective_score: float
    portfolio_risk_pct: float
    selected_count: int
    confidence_score: float
    recommendation_grade: str
    risk_severity: str
    allowed: bool
    valid: bool
    recommended_policy: Any = None
    rejection_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

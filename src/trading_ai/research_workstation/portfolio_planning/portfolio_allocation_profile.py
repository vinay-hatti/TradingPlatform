from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AllocationCandidateProfile:
    candidate_id: str
    symbol: str
    sector: str
    strategy_name: str
    requested_contracts: int
    maximum_contracts: int
    risk_per_contract: float
    buying_power_per_contract: float
    maximum_profit_per_contract: float
    probability_of_profit: float
    expected_return_pct: float
    annualized_volatility_pct: float
    expected_shortfall_per_contract: float
    liquidity_score: float
    delta_per_contract: float = 0.0
    gamma_per_contract: float = 0.0
    theta_per_contract: float = 0.0
    vega_per_contract: float = 0.0
    direction: str = "NEUTRAL"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PositionSizingProfile:
    candidate_id: str
    fixed_fractional_contracts: int
    kelly_fraction: float
    kelly_contracts: int
    volatility_target_contracts: int
    risk_budget_contracts: int
    expected_shortfall_contracts: int
    liquidity_adjusted_contracts: int
    recommended_contracts: int
    binding_constraint: str
    liquidity_haircut: float
    maximum_position_risk: float
    maximum_position_buying_power: float


@dataclass(frozen=True)
class AllocationDecisionProfile:
    candidate_id: str
    symbol: str
    sector: str
    strategy_name: str
    allocated_contracts: int
    allocated_risk: float
    allocated_buying_power: float
    expected_profit: float
    expected_return_pct: float
    allocation_status: str
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExposureAnalyticsProfile:
    portfolio_delta: float
    portfolio_gamma: float
    portfolio_theta: float
    portfolio_vega: float
    gross_directional_exposure: float
    net_directional_exposure: float
    total_risk: float
    total_buying_power: float
    total_expected_profit: float
    sector_exposure: dict[str, float]
    strategy_exposure: dict[str, float]
    symbol_exposure: dict[str, float]


@dataclass(frozen=True)
class PortfolioHealthProfile:
    capital_utilization_pct: float
    portfolio_risk_pct: float
    remaining_buying_power: float
    diversification_score: float
    concentration_score: float
    liquidity_score: float
    expected_return_score: float
    portfolio_health_score: float
    portfolio_health_grade: str
    risk_severity: str


@dataclass(frozen=True)
class PortfolioAllocationProfile:
    account_equity: float
    candidates_evaluated: int
    positions_allocated: int
    sizing_profiles: tuple[PositionSizingProfile, ...]
    decisions: tuple[AllocationDecisionProfile, ...]
    exposure: ExposureAnalyticsProfile
    health: PortfolioHealthProfile
    allowed: bool
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

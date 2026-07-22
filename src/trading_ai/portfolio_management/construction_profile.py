from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class PortfolioConstructionPolicyProfile:
    portfolio_id: str = "PRIMARY"
    minimum_ranking_score: float = 60.0
    minimum_strategy_score: float = 65.0
    minimum_portfolio_fit_score: float = 40.0
    maximum_new_positions: int = 10
    require_allowed: bool = True
    require_selected: bool = False
    allowed_readiness: tuple[str, ...] = ("READY", "EXECUTION_READY", "APPROVED")
    allow_research_positions: bool = False
    allow_undefined_risk: bool = False
    reserve_cash_pct: float = 0.20
    maximum_portfolio_exposure_pct: float = 0.50
    maximum_total_risk_pct: float = 0.20
    maximum_position_pct: float = 0.10
    maximum_risk_per_trade_pct: float = 0.03
    maximum_positions_per_symbol: int = 1
    maximum_positions_per_sector: int = 3
    maximum_positions_per_strategy: int = 3
    maximum_positions_per_direction: int = 5
    maximum_positions_per_correlation_group: int = 2
    maximum_symbol_exposure_pct: float = 0.12
    maximum_sector_exposure_pct: float = 0.30
    maximum_strategy_exposure_pct: float = 0.35
    maximum_direction_exposure_pct: float = 0.60
    maximum_correlation_group_exposure_pct: float = 0.25
    maximum_absolute_delta: float = 500.0
    maximum_absolute_gamma: float = 25.0
    maximum_absolute_theta: float = 1000.0
    maximum_absolute_vega: float = 2500.0
    maximum_absolute_rho: float = 2500.0
    minimum_net_delta: float = -500.0
    maximum_net_delta: float = 500.0
    minimum_position_dollars: float = 100.0
    maximum_contracts_per_position: int = 20
    use_risk_based_sizing: bool = True
    use_score_scaling: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NormalizedPortfolioCandidate:
    candidate_id: str
    symbol: str
    strategy: str
    direction: str
    ranking_score: float
    raw_ranking_score: float
    strategy_score: float
    portfolio_fit_score: float
    expected_return_pct: float
    expected_profit: float
    maximum_loss: float
    capital_required: float
    allowed: bool
    selected: bool
    readiness: str
    action: str
    recommendation: str
    market_regime: str = "UNKNOWN"
    probability_of_profit: float | None = None
    sector: str = "UNKNOWN"
    industry: str = "UNKNOWN"
    correlation_group: str = ""
    expiry: str = ""
    dte: int = 0
    strike: float | None = None
    long_strike: float | None = None
    short_strike: float | None = None
    option_symbol: str = ""
    premium_type: str = ""
    risk_profile: str = "DEFINED_RISK"
    complexity: str = "STANDARD"
    greeks: dict[str, float] = field(default_factory=dict)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    rejection_reasons: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PortfolioConstructionRun:
    run_id: str
    portfolio_id: str
    status: str
    readiness: str
    candidate_count: int
    eligible_candidate_count: int
    proposed_position_count: int
    rejected_candidate_count: int
    existing_position_count: int
    net_liquidation_value: float
    cash_balance: float
    existing_capital_committed: float
    available_capital: float
    proposed_capital: float
    combined_capital: float
    portfolio_score: float
    diversification_score: float
    risk_score: float
    capital_efficiency_score: float
    proposed_positions: tuple[dict[str, Any], ...]
    rejections: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    recommendations: tuple[str, ...]
    policy: dict[str, Any]
    generated_at: str
    source_file: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

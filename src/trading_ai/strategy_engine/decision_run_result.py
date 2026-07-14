from dataclasses import dataclass, field
from typing import Any

from trading_ai.strategy_engine.decision_candidate_bundle import (
    DecisionCandidateBundle,
)
from trading_ai.strategy_engine.institutional_decision import (
    InstitutionalDecision,
)


@dataclass
class SymbolDecisionDiagnostic:
    symbol: str

    processed: bool
    candidate_count: int
    accepted_candidate_count: int
    rejected_candidate_count: int

    errors: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )


@dataclass
class DecisionRunResult:
    decisions: list[InstitutionalDecision]

    selected_decisions: list[InstitutionalDecision]
    rejected_decisions: list[InstitutionalDecision]

    candidate_bundles: list[DecisionCandidateBundle]

    ranked_opportunities: list[Any]

    portfolio_result: Any

    symbol_diagnostics: list[
        SymbolDecisionDiagnostic
    ]

    total_symbols: int
    processed_symbols: int

    total_candidates: int
    accepted_candidates: int
    rejected_candidates: int

    selected_count: int

    overall_readiness: str
    overall_action: str

    valid: bool

    portfolio_risk_surface_profile: Any = None

    portfolio_optimization_profile: Any = None

    portfolio_optimization_frontier_profile: Any = None

    portfolio_optimization_recommendation: Any = None

    probability_calibration_model_family: Any = None
    probability_calibration_model_version: str = "UNAVAILABLE"

    walk_forward_profile: Any = None
    walk_forward_calibration_profile: Any = None

    market_regime_profiles: Any = None
    market_regime_forecast_profiles: Any = None
    market_breadth_profile: Any = None

    execution_integration_profile: Any = None
    execution_aggregation_profile: Any = None
    execution_benchmark_profile: Any = None
    execution_routing_profile: Any = None

    warnings: list[str] = field(
        default_factory=list
    )

    errors: list[str] = field(
        default_factory=list
    )

    metadata: dict = field(
        default_factory=dict
    )

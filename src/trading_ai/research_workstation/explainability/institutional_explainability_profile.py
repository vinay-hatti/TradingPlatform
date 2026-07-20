from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DecisionFactorProfile:
    name: str
    category: str
    raw_score: float
    weight: float
    weighted_contribution: float
    direction: str
    materiality: str
    rationale: str


@dataclass(frozen=True)
class ScenarioDefinitionProfile:
    name: str
    description: str
    price_shock_pct: float = 0.0
    volatility_shock_points: float = 0.0
    days_elapsed: int = 0
    probability_weight: float = 0.0


@dataclass(frozen=True)
class ScenarioOutcomeProfile:
    name: str
    underlying_price: float
    projected_profit_loss: float
    projected_return_on_risk: float
    delta_effect: float
    gamma_effect: float
    theta_effect: float
    vega_effect: float
    total_greeks_effect: float
    risk_level: str
    favorable: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioComparisonProfile:
    best_scenario: str
    worst_scenario: str
    best_projected_profit_loss: float
    worst_projected_profit_loss: float
    payoff_range: float
    favorable_scenario_count: int
    adverse_scenario_count: int
    high_risk_scenario_count: int
    probability_weighted_profit_loss: float


@dataclass(frozen=True)
class ScenarioAnalysisProfile:
    definitions: tuple[ScenarioDefinitionProfile, ...]
    outcomes: tuple[ScenarioOutcomeProfile, ...]
    comparison: ScenarioComparisonProfile


@dataclass(frozen=True)
class InstitutionalExplainabilityProfile:
    symbol: str
    strategy: str
    recommendation: str
    approval_status: str
    explainability_score: float
    confidence: float
    factor_contributions: tuple[DecisionFactorProfile, ...]
    primary_drivers: tuple[str, ...]
    primary_risks: tuple[str, ...]
    scenario_analysis: ScenarioAnalysisProfile
    decision_summary: str
    audit_narrative: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SensitivityDimensionProfile:
    dimension: str
    baseline_value: float
    stressed_value: float
    absolute_change: float
    relative_change: float
    classification: str
    score_impact: float
    notes: str


@dataclass(frozen=True)
class ExpectedValueBreakdownProfile:
    scenario_id: str
    scenario_name: str
    probability: float
    expected_return_pct: float
    weighted_return_pct: float
    weighted_volatility_pct: float
    weighted_drawdown_pct: float


@dataclass(frozen=True)
class ScenarioDeltaProfile:
    left_scenario_id: str
    right_scenario_id: str
    return_delta_pct: float
    volatility_delta_pct: float
    drawdown_delta_pct: float
    probability_delta: float
    dominance: str


@dataclass(frozen=True)
class ScenarioRankingProfile:
    rank: int
    scenario_id: str
    scenario_name: str
    scenario_type: str
    composite_score: float
    expected_return_pct: float
    expected_volatility_pct: float
    expected_drawdown_pct: float
    probability: float
    confidence_adjusted_score: float
    rank_reason: str


@dataclass(frozen=True)
class RecommendationProfile:
    action: str
    confidence: float
    recommendation_score: float
    rationale: str
    primary_drivers: tuple[str, ...]
    key_risks: tuple[str, ...]
    monitoring_requirements: tuple[str, ...]


@dataclass(frozen=True)
class ScenarioComparisonProfile:
    case_id: str
    symbol: str
    strategy_name: str
    status: str
    comparison_score: float
    comparison_grade: str
    probability_total: float
    weighted_expected_return_pct: float
    weighted_expected_volatility_pct: float
    weighted_expected_drawdown_pct: float
    best_scenario_id: str | None
    worst_scenario_id: str | None
    rankings: tuple[ScenarioRankingProfile, ...]
    expected_value_breakdown: tuple[
        ExpectedValueBreakdownProfile, ...
    ]
    scenario_deltas: tuple[ScenarioDeltaProfile, ...]
    sensitivities: tuple[SensitivityDimensionProfile, ...]
    recommendation: RecommendationProfile
    positive_factors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    remediation_actions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

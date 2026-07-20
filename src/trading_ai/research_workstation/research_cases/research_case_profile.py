from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class ResearchEvidenceProfile:
    evidence_id: str
    category: str
    description: str
    source: str
    observed_at: datetime
    reliability_score: float
    supports_thesis: bool
    notes: str | None = None


@dataclass(frozen=True)
class ResearchAssumptionProfile:
    assumption_id: str
    description: str
    importance: str
    confidence: float
    validation_method: str
    invalidation_condition: str


@dataclass(frozen=True)
class ResearchScenarioProfile:
    scenario_id: str
    name: str
    scenario_type: str
    probability: float
    expected_return_pct: float
    expected_volatility_pct: float
    expected_drawdown_pct: float
    expected_holding_days: int
    thesis: str
    catalysts: tuple[str, ...]
    risks: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    recommended_action: str


@dataclass(frozen=True)
class ResearchCaseProfile:
    case_id: str
    symbol: str
    strategy_name: str
    title: str
    primary_thesis: str
    time_horizon: str
    review_date: date
    status: str
    confidence_score: float
    research_score: float
    research_grade: str
    scenario_probability_total: float
    expected_return_pct: float
    expected_volatility_pct: float
    expected_drawdown_pct: float
    scenarios: tuple[ResearchScenarioProfile, ...]
    evidence: tuple[ResearchEvidenceProfile, ...]
    assumptions: tuple[ResearchAssumptionProfile, ...]
    positive_factors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    remediation_actions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

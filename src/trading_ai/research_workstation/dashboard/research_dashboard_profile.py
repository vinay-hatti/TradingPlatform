from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass(frozen=True)
class KPIProfile:
    name: str
    score: float
    grade: str
    status: str
    explanation: str

@dataclass(frozen=True)
class ResearchScorecardProfile:
    kpis: tuple[KPIProfile, ...]
    overall_score: float
    overall_grade: str
    institutional_ready: bool

@dataclass(frozen=True)
class ExecutiveSummaryProfile:
    recommendation: str
    research_status: str
    confidence_summary: str
    executive_conclusion: str
    key_strengths: tuple[str, ...]
    key_risks: tuple[str, ...]
    required_actions: tuple[str, ...]

@dataclass(frozen=True)
class DashboardSectionProfile:
    section_id: str
    title: str
    status: str
    summary: str
    metrics: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PhaseCompletionProfile:
    phase_status: str
    completeness_score: float
    required_artifacts_present: tuple[str, ...]
    missing_artifacts: tuple[str, ...]
    consistency_errors: tuple[str, ...]
    regression_ready: bool

@dataclass(frozen=True)
class ResearchDashboardProfile:
    dashboard_id: str
    generated_at: datetime
    case_id: str
    journal_id: str
    symbol: str
    strategy_name: str
    executive_summary: ExecutiveSummaryProfile
    scorecard: ResearchScorecardProfile
    sections: tuple[DashboardSectionProfile, ...]
    phase_completion: PhaseCompletionProfile
    source_artifacts: dict[str, str]
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

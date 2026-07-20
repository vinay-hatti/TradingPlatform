from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class DashboardMetricProfile:
    name: str
    value: float
    status: str
    detail: str


@dataclass(frozen=True)
class KnowledgeDashboardProfile:
    dashboard_id: str
    generated_at: datetime
    milestone: int
    phase: int
    research_case_count: int
    pattern_cluster_count: int
    institutional_learning_case_count: int
    analyst_count: int
    governance_status: str
    readiness_score: float
    readiness_grade: str
    metrics: tuple[DashboardMetricProfile, ...]
    highlights: tuple[str, ...]
    risks: tuple[str, ...]
    source_status: dict[str, str]
    metadata: dict[str, Any] = field(default_factory=dict)

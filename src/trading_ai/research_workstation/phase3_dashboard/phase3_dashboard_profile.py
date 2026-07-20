from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DashboardMetricProfile:
    key: str
    label: str
    value: str
    status: str
    severity: str
    description: str


@dataclass(frozen=True)
class DashboardSectionProfile:
    section_id: str
    title: str
    status: str
    score: float
    grade: str
    metrics: tuple[DashboardMetricProfile, ...]
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class Phase3DashboardProfile:
    trade_id: str
    symbol: str
    strategy_name: str
    overall_status: str
    overall_score: float
    overall_grade: str
    risk_severity: str
    execution_allowed: bool
    sections: tuple[DashboardSectionProfile, ...]
    approval_status: str
    approval_recommendation: str
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    remediation_actions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

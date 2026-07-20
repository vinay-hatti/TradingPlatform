from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class KpiMetric(BaseModel):
    metric_id: str
    label: str
    value: float
    unit: str = ""
    status: Literal["GOOD", "WATCH", "BAD", "UNKNOWN"] = "UNKNOWN"
    period: str = "CURRENT"
    source: str = ""


class ExecutiveScorecard(BaseModel):
    generated_at: datetime
    as_of_date: date
    total_net_pnl: float = 0
    gross_exposure: float = 0
    net_exposure: float = 0
    win_rate: float = 0
    sharpe_ratio: float = 0
    max_drawdown: float = 0
    active_strategies: int = 0
    active_incidents: int = 0
    critical_alerts: int = 0
    open_access_reviews: int = 0
    kpis: list[KpiMetric] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BoardSection(BaseModel):
    title: str
    summary: str
    highlights: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class BoardReport(BaseModel):
    generated_at: datetime
    title: str
    reporting_period: str
    executive_summary: str
    sections: list[BoardSection]
    approvals: list[str] = Field(default_factory=list)
    source_artifacts: list[str] = Field(default_factory=list)


class RegulatoryExportRequest(BaseModel):
    export_type: Literal[
        "RISK_SUMMARY",
        "EXECUTION_ACTIVITY",
        "GOVERNANCE_AUDIT",
        "ACCESS_REVIEW",
        "FULL_EVIDENCE_PACKAGE",
    ]
    start_date: date | None = None
    end_date: date | None = None
    include_source_paths: bool = True


class RegulatoryExportRecord(BaseModel):
    export_id: str
    export_type: str
    generated_at: datetime
    start_date: date | None = None
    end_date: date | None = None
    record_count: int = 0
    checksum: str
    output_path: str
    warnings: list[str] = Field(default_factory=list)

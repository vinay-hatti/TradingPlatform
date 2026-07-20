from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Phase3PipelineResultProfile:
    trade_id: str
    symbol: str
    strategy_name: str
    output_directory: Path
    trade_construction_report: Path
    portfolio_allocation_report: Path
    trade_lifecycle_report: Path
    pretrade_governance_report: Path
    dashboard_json_report: Path
    dashboard_html_report: Path
    pipeline_report: Path
    overall_status: str
    approval_status: str
    execution_allowed: bool
    metadata: dict[str, Any] = field(default_factory=dict)

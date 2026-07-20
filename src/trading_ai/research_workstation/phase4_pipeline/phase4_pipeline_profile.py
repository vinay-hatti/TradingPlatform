from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Phase4PipelineResultProfile:
    case_id: str
    symbol: str
    strategy_name: str
    output_directory: Path
    research_case_report: Path
    scenario_comparison_report: Path
    pipeline_report: Path
    research_case_status: str
    scenario_comparison_status: str
    recommendation_action: str
    metadata: dict[str, Any] = field(default_factory=dict)

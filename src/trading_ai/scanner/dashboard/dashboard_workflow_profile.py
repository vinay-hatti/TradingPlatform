from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class DashboardWorkflowStage:
    name: str
    status: str
    artifact_path: str | None
    summary: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "artifact_path": self.artifact_path,
            "summary": dict(self.summary),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class DashboardWorkflowReport:
    generated_at: str
    symbol: str
    direction: str
    workflow_status: str
    completed_stages: int
    total_stages: int
    paper_trade_ready: bool
    position_open: bool
    performance_available: bool
    stages: tuple[DashboardWorkflowStage, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "symbol": self.symbol,
            "direction": self.direction,
            "workflow_status": self.workflow_status,
            "completed_stages": self.completed_stages,
            "total_stages": self.total_stages,
            "paper_trade_ready": self.paper_trade_ready,
            "position_open": self.position_open,
            "performance_available": self.performance_available,
            "stages": [stage.to_dict() for stage in self.stages],
            "warnings": list(self.warnings),
        }

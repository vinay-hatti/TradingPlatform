from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

class DeploymentStrategy(str, Enum):
    BLUE_GREEN = "BLUE_GREEN"
    CANARY = "CANARY"
    IN_PLACE = "IN_PLACE"

class AutomationStatus(str, Enum):
    CREATED = "CREATED"
    PREPARING = "PREPARING"
    DEPLOYING = "DEPLOYING"
    OBSERVING = "OBSERVING"
    PROMOTING = "PROMOTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class HealthGateResult:
    healthy: bool
    score: float
    reason: str
    metrics: dict[str, float] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

@dataclass(frozen=True)
class DeploymentStageResult:
    stage_name: str
    status: str
    message: str
    started_at: str
    completed_at: str
    details: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class DeploymentAutomationResult:
    deployment_id: str
    release_id: str
    environment: str
    strategy: str
    status: str
    active_slot: str | None
    candidate_slot: str | None
    traffic_percent: int
    rollback_executed: bool
    stages: tuple[DeploymentStageResult, ...]
    recommendation: str
    started_at: str
    completed_at: str

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class PipelineStage(str, Enum):
    INITIALIZING = "INITIALIZING"
    BUILDING_UNIVERSE = "BUILDING_UNIVERSE"
    POPULATING_MARKET_DATA = "POPULATING_MARKET_DATA"
    BUILDING_LIQUIDITY_METRICS = "BUILDING_LIQUIDITY_METRICS"
    SCREENING_LIQUIDITY = "SCREENING_LIQUIDITY"
    VALIDATING_PUBLICATION = "VALIDATING_PUBLICATION"
    REPORTING = "REPORTING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


@dataclass(frozen=True)
class PipelineStageResult:
    stage: str
    status: str
    started_at: datetime
    completed_at: datetime
    elapsed_seconds: float
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArtifactHealth:
    name: str
    path: str
    exists: bool
    size_bytes: int
    sha256: str
    expected_sha256: str = ""
    checksum_valid: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UniversePipelineResult:
    run_id: str
    started_at: datetime
    completed_at: datetime
    status: str
    last_completed_stage: str
    elapsed_seconds: float
    universe_count: int
    metrics_count: int
    eligible_count: int
    rejected_count: int
    review_count: int
    stage_results: tuple[PipelineStageResult, ...]
    artifacts: tuple[ArtifactHealth, ...]
    warnings: tuple[str, ...] = ()
    error: str = ""
    resumed: bool = False
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "stage_results": [item.to_dict() for item in self.stage_results],
            "artifacts": [item.to_dict() for item in self.artifacts],
        }

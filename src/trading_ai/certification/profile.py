from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class CertificationCheck:
    code: str
    name: str
    status: str
    severity: str
    message: str
    blocking: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CertificationPolicy:
    expected_alembic_head: str = "m47_002"
    publication_name: str = "current_market_state"
    require_ready_or_degraded_publication: bool = True
    require_scanner_ready: bool = True
    require_decision_ready: bool = True
    require_option_snapshot: bool = True
    require_scanner_lineage: bool = True
    require_candidate_lineage: bool = True
    require_decision_lineage: bool = False
    require_replay_history: bool = False
    require_zero_latest_replay_mismatches: bool = True
    require_manifest_integrity: bool = True
    report_version: str = "m47.phase8.v1"


@dataclass(frozen=True)
class CertificationResult:
    certification_run_id: str
    status: str
    started_at: datetime
    completed_at: datetime
    checks: tuple[CertificationCheck, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == "CERTIFIED"

    @property
    def blocking_failures(self) -> tuple[CertificationCheck, ...]:
        return tuple(item for item in self.checks if item.blocking and item.status == "FAILED")

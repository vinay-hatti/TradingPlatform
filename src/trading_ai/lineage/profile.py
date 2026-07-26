from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ScannerRunLineage:
    scanner_run_id: str
    publication_name: str | None
    ingestion_run_id: str | None
    publication_status: str
    published_at: str | None
    market_as_of_date: str | None
    market_intelligence_snapshot_timestamp: str | None
    option_snapshot_timestamp: str | None
    option_snapshot_id: str | None
    option_snapshot_completeness_pct: float | None
    published_state_degraded: bool
    scanner_version: str
    started_at: datetime


@dataclass(frozen=True)
class DecisionRunLineage:
    decision_run_id: str
    publication_name: str | None
    ingestion_run_id: str | None
    publication_status: str
    market_intelligence_snapshot_timestamp: str | None
    option_snapshot_timestamp: str | None
    option_snapshot_id: str | None
    published_state_degraded: bool
    decision_engine_version: str
    policy_version: str
    started_at: datetime


@dataclass(frozen=True)
class PersistenceSummary:
    run_id: str
    run_rows: int
    item_rows: int
    status: str
    metadata: dict[str, Any]

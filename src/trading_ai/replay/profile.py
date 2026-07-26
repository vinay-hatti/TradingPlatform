from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class ReplaySelector:
    scanner_run_id: str | None = None
    decision_run_id: str | None = None
    ingestion_run_id: str | None = None
    publication_name: str | None = None

    def validate(self) -> None:
        values = [self.scanner_run_id, self.decision_run_id, self.ingestion_run_id, self.publication_name]
        if not any(values):
            raise ValueError("At least one replay selector must be supplied")


@dataclass(frozen=True)
class ReplayPolicy:
    require_exact_market_state_hash: bool = True
    require_candidate_match: bool = True
    require_decision_match: bool = True
    allow_missing_decisions: bool = True
    persist_replay: bool = True
    report_version: str = "m47.phase7.v1"


@dataclass(frozen=True)
class ReplaySource:
    publication_name: str | None
    ingestion_run_id: str | None
    publication_status: str
    market_as_of_date: str | None
    market_intelligence_snapshot_timestamp: str | None
    option_snapshot_timestamp: str | None
    option_snapshot_id: str | None
    market_state_hash: str | None
    scanner_run_id: str | None
    scanner_version: str | None
    decision_run_id: str | None
    decision_engine_version: str | None
    policy_version: str | None
    scanner_candidates: tuple[dict[str, Any], ...] = ()
    decisions: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class ReplayComparison:
    category: str
    key: str
    status: str
    baseline_hash: str | None
    replay_hash: str | None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReplayResult:
    replay_run_id: str
    mode: str
    status: str
    started_at: datetime
    completed_at: datetime
    source: ReplaySource
    replay_candidates: tuple[dict[str, Any], ...]
    replay_decisions: tuple[dict[str, Any], ...]
    comparisons: tuple[ReplayComparison, ...]
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def matched(self) -> bool:
        return all(item.status == "MATCH" for item in self.comparisons)


ScannerReplayExecutor = Callable[[ReplaySource], Iterable[Any]]
DecisionReplayExecutor = Callable[[ReplaySource, Iterable[dict[str, Any]]], Iterable[Any]]

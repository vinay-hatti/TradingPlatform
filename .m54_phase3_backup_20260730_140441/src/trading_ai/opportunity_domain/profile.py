from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class WorkflowState(StrEnum):
    STAGED = "STAGED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TRADE_BUILT = "TRADE_BUILT"
    PAPER_SUBMITTED = "PAPER_SUBMITTED"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True, slots=True)
class OpportunityCreate:
    scanner_run_id: str
    snapshot_id: str
    snapshot_timestamp: str
    symbol: str
    direction: str
    strategy: str
    source_payload: dict[str, Any]
    created_by: str = "option-scanner"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OpportunityTransition:
    new_state: WorkflowState
    actor: str
    reason: str
    expected_version: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OpportunityRecord:
    opportunity_id: str
    scanner_run_id: str
    snapshot_id: str
    snapshot_timestamp: str
    symbol: str
    direction: str
    strategy: str
    workflow_state: WorkflowState
    version: int
    source_payload: dict[str, Any]
    created_by: str
    created_at: str
    updated_at: str
    metadata: dict[str, Any]

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ThesisRevisionProfile:
    revision_id: str
    revised_at: datetime
    previous_thesis: str
    revised_thesis: str
    revision_reason: str
    author: str
    material_change: bool


@dataclass(frozen=True)
class DecisionReviewProfile:
    review_id: str
    reviewer: str
    reviewed_at: datetime
    review_status: str
    reviewer_confidence: float
    comments: str
    required_actions: tuple[str, ...]
    execution_approved: bool


@dataclass(frozen=True)
class DecisionJournalEntryProfile:
    entry_id: str
    entry_type: str
    recorded_at: datetime
    actor: str
    summary: str
    details: str
    prior_status: str | None
    resulting_status: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionJournalProfile:
    journal_id: str
    case_id: str
    symbol: str
    strategy_name: str
    decision_action: str
    decision_status: str
    decision_confidence: float
    decision_rationale: str
    primary_risks: tuple[str, ...]
    monitoring_plan: tuple[str, ...]
    selected_scenario_id: str | None
    execution_allowed: bool
    approval_status: str
    current_thesis: str
    thesis_revisions: tuple[ThesisRevisionProfile, ...]
    reviews: tuple[DecisionReviewProfile, ...]
    entries: tuple[DecisionJournalEntryProfile, ...]
    positive_factors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    remediation_actions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

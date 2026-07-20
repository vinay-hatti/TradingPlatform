from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ResearchTagProfile:
    tag: str
    category: str
    confidence: float
    source: str


@dataclass(frozen=True)
class KnowledgeRecordProfile:
    record_id: str
    record_type: str
    title: str
    summary: str
    source_reference: str
    quality_score: float
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeCaseProfile:
    knowledge_case_id: str
    case_id: str
    symbol: str
    strategy_name: str
    sector: str
    industry: str
    primary_thesis: str
    decision_action: str
    decision_status: str
    outcome_status: str
    thesis_validation_status: str
    institutional_score: float
    case_completeness_score: float
    evidence_quality_score: float
    tags: tuple[ResearchTagProfile, ...]
    records: tuple[KnowledgeRecordProfile, ...]
    positive_factors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    remediation_actions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeIndexProfile:
    symbols: dict[str, tuple[str, ...]]
    sectors: dict[str, tuple[str, ...]]
    strategies: dict[str, tuple[str, ...]]
    tags: dict[str, tuple[str, ...]]
    outcomes: dict[str, tuple[str, ...]]
    thesis_statuses: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class ResearchKnowledgeBaseProfile:
    knowledge_base_id: str
    generated_at: datetime
    case_count: int
    record_count: int
    tag_count: int
    cases: tuple[KnowledgeCaseProfile, ...]
    index: KnowledgeIndexProfile
    governance_status: str
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

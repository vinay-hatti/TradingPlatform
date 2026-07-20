from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass(frozen=True)
class SimilarityMatchProfile:
    case_id: str
    matched_case_id: str
    similarity_score: float
    similarity_band: str
    shared_tags: tuple[str, ...]
    matched_dimensions: tuple[str, ...]
    outcome_status: str
    thesis_validation_status: str
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class SimilarityReportProfile:
    report_id: str
    generated_at: datetime
    case_count: int
    match_count: int
    matches: tuple[SimilarityMatchProfile, ...]
    governance_status: str
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PatternClusterProfile:
    cluster_id: str
    cluster_type: str
    cluster_key: str
    case_ids: tuple[str, ...]
    case_count: int
    dominant_outcome: str
    dominant_thesis_status: str
    average_institutional_score: float
    success_rate: float
    shared_tags: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class PatternDiscoveryProfile:
    report_id: str
    generated_at: datetime
    cluster_count: int
    clusters: tuple[PatternClusterProfile, ...]
    strongest_patterns: tuple[str, ...]
    warnings: tuple[str, ...]
    governance_status: str
    metadata: dict[str, Any] = field(default_factory=dict)

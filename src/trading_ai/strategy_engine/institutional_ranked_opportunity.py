from dataclasses import dataclass, field

from trading_ai.strategy_engine.institutional_opportunity import (
    InstitutionalOpportunity,
)
from trading_ai.strategy_engine.institutional_rank_breakdown import (
    InstitutionalRankBreakdown,
)


@dataclass
class InstitutionalRankedOpportunity:
    rank: int

    opportunity: InstitutionalOpportunity
    ranking_score: float
    raw_ranking_score: float

    grade: str
    tier: str
    action: str

    selected: bool
    allowed: bool

    primary_reason: str
    diversification_reason: str

    rejection_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)

    breakdown: InstitutionalRankBreakdown | None = None
    metadata: dict = field(default_factory=dict)

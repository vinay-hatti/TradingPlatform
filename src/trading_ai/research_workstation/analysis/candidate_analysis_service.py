from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from trading_ai.research_workstation.scanner.market_scanner_profile import (
    MarketCandidateProfile,
    RankedMarketCandidateProfile,
)

from .candidate_analysis_engine import CandidateAnalysisEngine
from .candidate_analysis_profile import CandidateAnalysisProfile


class CandidateAnalysisService:
    def __init__(
        self,
        engine: CandidateAnalysisEngine | None = None,
    ):
        self.engine = engine or CandidateAnalysisEngine()

    def analyze_candidate(
        self,
        candidate: MarketCandidateProfile,
        *,
        composite_score: float | None = None,
    ) -> CandidateAnalysisProfile:
        return self.engine.analyze(
            candidate,
            composite_score=composite_score,
        )

    def analyze_ranked_candidate(
        self,
        candidate: RankedMarketCandidateProfile,
    ) -> CandidateAnalysisProfile:
        return self.engine.analyze(
            candidate.source,
            composite_score=candidate.composite_score,
        )

    def analyze_many(
        self,
        candidates: Sequence[
            MarketCandidateProfile | RankedMarketCandidateProfile
        ],
    ) -> tuple[CandidateAnalysisProfile, ...]:
        analyses = []
        for candidate in candidates:
            if isinstance(candidate, RankedMarketCandidateProfile):
                analyses.append(self.analyze_ranked_candidate(candidate))
            else:
                analyses.append(self.analyze_candidate(candidate))
        return tuple(analyses)

    def enrich_candidate(
        self,
        candidate: MarketCandidateProfile,
        *,
        composite_score: float | None = None,
    ) -> MarketCandidateProfile:
        analysis = self.analyze_candidate(
            candidate,
            composite_score=composite_score,
        )
        metadata = dict(candidate.metadata)
        metadata["candidate_analysis"] = analysis
        return replace(candidate, metadata=metadata)

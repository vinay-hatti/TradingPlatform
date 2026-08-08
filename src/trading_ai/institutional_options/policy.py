from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .domain import (
    ContractRecommendation,
    InstitutionalOpportunity,
    OpportunityState,
    OpportunityThesis,
    StrategyCandidate,
    StrategyDisposition,
    ensure_unique_contract_symbols,
)


_ALLOWED_TRANSITIONS: dict[OpportunityState, frozenset[OpportunityState]] = {
    OpportunityState.DISCOVERED: frozenset({OpportunityState.VALIDATED, OpportunityState.REJECTED, OpportunityState.CANCELLED}),
    OpportunityState.VALIDATED: frozenset({OpportunityState.STRATEGIES_GENERATED, OpportunityState.REJECTED, OpportunityState.CANCELLED}),
    OpportunityState.STRATEGIES_GENERATED: frozenset({OpportunityState.CONTRACTS_OPTIMIZED, OpportunityState.REJECTED, OpportunityState.CANCELLED}),
    OpportunityState.CONTRACTS_OPTIMIZED: frozenset({OpportunityState.READY_FOR_EXECUTION, OpportunityState.REJECTED, OpportunityState.CANCELLED}),
    OpportunityState.READY_FOR_EXECUTION: frozenset({OpportunityState.EXECUTED, OpportunityState.CANCELLED}),
    OpportunityState.EXECUTED: frozenset({OpportunityState.ACTIVE, OpportunityState.CLOSED}),
    OpportunityState.ACTIVE: frozenset({OpportunityState.CLOSED}),
    OpportunityState.CLOSED: frozenset({OpportunityState.ATTRIBUTED}),
    OpportunityState.ATTRIBUTED: frozenset(),
    OpportunityState.REJECTED: frozenset(),
    OpportunityState.CANCELLED: frozenset(),
}


@dataclass(frozen=True)
class OpportunityGovernancePolicy:
    minimum_underlying_score: float = 55.0
    minimum_confidence: float = 55.0
    minimum_strategy_eligibility_score: float = 50.0
    require_polygon_lineage: bool = True
    policy_version: str = "M62-PH1-1.0"

    def validate_transition(self, current: OpportunityState, target: OpportunityState) -> None:
        if target not in _ALLOWED_TRANSITIONS[current]:
            raise ValueError(f"Invalid Institutional Opportunity transition: {current.value} -> {target.value}")

    def validate_opportunity(self, opportunity: InstitutionalOpportunity, thesis: OpportunityThesis) -> None:
        if opportunity.symbol.strip() == "":
            raise ValueError("Institutional Opportunity symbol is required")
        if opportunity.overall_score < self.minimum_underlying_score:
            raise ValueError("Underlying opportunity score is below policy minimum")
        if opportunity.confidence < self.minimum_confidence:
            raise ValueError("Underlying opportunity confidence is below policy minimum")
        if opportunity.thesis_id != thesis.thesis_id or thesis.opportunity_id != opportunity.opportunity_id:
            raise ValueError("Opportunity and thesis identity mismatch")
        if thesis.entry_zone_low > thesis.entry_zone_high:
            raise ValueError("Opportunity thesis entry zone is invalid")
        if not thesis.targets:
            raise ValueError("Opportunity thesis requires at least one dynamic underlying target")
        if self.require_polygon_lineage and not opportunity.lineage.source_provider.upper().startswith("POLYGON"):
            raise ValueError("Milestone 62 requires Polygon-backed opportunity lineage")

    def validate_strategy_evaluations(self, candidates: Iterable[StrategyCandidate]) -> None:
        candidate_list = list(candidates)
        if not candidate_list:
            raise ValueError("At least one strategy candidate is required")
        ids = [item.strategy_candidate_id for item in candidate_list]
        if len(ids) != len(set(ids)):
            raise ValueError("Strategy candidate identifiers must be unique")

    def validate_strategy_candidates(self, candidates: Iterable[StrategyCandidate]) -> None:
        candidate_list = list(candidates)
        self.validate_strategy_evaluations(candidate_list)
        eligible = [item for item in candidate_list if item.disposition != StrategyDisposition.REJECTED]
        if not eligible:
            raise ValueError("At least one eligible strategy candidate is required")

    def validate_contract_recommendation(self, recommendation: ContractRecommendation) -> None:
        if not recommendation.option_snapshot_id:
            raise ValueError("Contract recommendation requires governed option snapshot lineage")
        if recommendation.legs:
            ensure_unique_contract_symbols(recommendation.legs)
        elif recommendation.executable:
            raise ValueError("Executable contract recommendation requires at least one exact option leg")
        elif not recommendation.validation_reasons:
            raise ValueError("Non-executable contract recommendation requires validation reasons")

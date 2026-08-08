from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from .domain import (
    ContractRecommendation,
    ExecutionRecommendation,
    InstitutionalOpportunity,
    OpportunityOutcomeAttribution,
    OpportunityState,
    OpportunityThesis,
    StrategyCandidate,
    StrategyComparison,
    serialize_domain,
)
from .models import (
    ContractRecommendationModel,
    ExecutionRecommendationModel,
    InstitutionalOpportunityAuditModel,
    InstitutionalOpportunityModel,
    OpportunityOutcomeAttributionModel,
    OpportunityThesisModel,
    StrategyCandidateModel,
    StrategyComparisonModel,
    StrategyValuationModel,
    PositionManagementSnapshotModel,
)
from .policy import OpportunityGovernancePolicy


class InstitutionalOpportunityRepository:
    def __init__(self, session: Session, policy: OpportunityGovernancePolicy | None = None) -> None:
        self.session = session
        self.policy = policy or OpportunityGovernancePolicy()

    def save_opportunity(self, opportunity: InstitutionalOpportunity, thesis: OpportunityThesis) -> None:
        self.policy.validate_opportunity(opportunity, thesis)
        lineage = opportunity.lineage
        self.session.merge(InstitutionalOpportunityModel(
            opportunity_id=opportunity.opportunity_id,
            symbol=opportunity.symbol,
            asset_class=opportunity.asset_class,
            state=opportunity.state.value,
            direction=opportunity.direction.value,
            category=opportunity.category,
            overall_score=opportunity.overall_score,
            confidence=opportunity.confidence,
            conviction=opportunity.conviction,
            thesis_id=opportunity.thesis_id,
            stock_publication_name=lineage.stock_publication_name,
            stock_scanner_run_id=lineage.stock_scanner_run_id,
            stock_candidate_id=lineage.stock_candidate_id,
            stock_state_hash=lineage.stock_state_hash,
            option_snapshot_id=lineage.option_snapshot_id,
            version=opportunity.version,
            created_at=opportunity.created_at,
            updated_at=opportunity.updated_at,
            payload_json=serialize_domain(opportunity),
        ))
        self.session.merge(OpportunityThesisModel(
            thesis_id=thesis.thesis_id,
            opportunity_id=thesis.opportunity_id,
            direction=thesis.direction.value,
            setup_category=thesis.setup_category,
            primary_timeframe=thesis.primary_timeframe,
            invalidation_level=thesis.invalidation_level,
            entry_zone_low=thesis.entry_zone_low,
            entry_zone_high=thesis.entry_zone_high,
            created_at=thesis.created_at,
            payload_json=serialize_domain(thesis),
        ))

    def transition(self, opportunity_id: str, target: OpportunityState, actor: str, reason: str) -> InstitutionalOpportunityModel:
        # Pending merge/add operations must be visible before lifecycle lookup.
        self.session.flush()
        row = self.session.get(InstitutionalOpportunityModel, opportunity_id)
        if row is None:
            raise LookupError(f"Institutional Opportunity not found: {opportunity_id}")
        current = OpportunityState(row.state)
        self.policy.validate_transition(current, target)
        row.state = target.value
        row.version += 1
        row.updated_at = datetime.now(timezone.utc).isoformat()
        self.session.add(InstitutionalOpportunityAuditModel(
            audit_id=f"m62-audit-{uuid4().hex}",
            opportunity_id=opportunity_id,
            previous_state=current.value,
            new_state=target.value,
            actor=actor,
            reason=reason,
            event_timestamp=row.updated_at,
            payload_json={"version": row.version},
        ))
        return row

    def _merge_strategy_candidates(self, candidates: list[StrategyCandidate]) -> None:
        """Upsert strategy evaluations by their database natural key.

        Strategy identifiers are generated for new evaluations, while the table
        enforces one row per ``(opportunity_id, strategy)``. Daily rebuilds must
        therefore preserve the existing identifier and refresh the row rather
        than attempting a second insert with a new primary key.
        """
        for candidate in candidates:
            existing = self.session.query(StrategyCandidateModel).filter_by(
                opportunity_id=candidate.opportunity_id,
                strategy=candidate.strategy,
            ).one_or_none()
            strategy_candidate_id = (
                existing.strategy_candidate_id
                if existing is not None
                else candidate.strategy_candidate_id
            )
            payload = serialize_domain(candidate)
            payload["strategy_candidate_id"] = strategy_candidate_id
            if existing is None:
                existing = StrategyCandidateModel(
                    strategy_candidate_id=strategy_candidate_id,
                    opportunity_id=candidate.opportunity_id,
                    strategy=candidate.strategy,
                    disposition=candidate.disposition.value,
                    eligibility_score=candidate.eligibility_score,
                    strategy_score=candidate.strategy_score,
                    complexity=candidate.complexity,
                    rank=candidate.rank,
                    selected=candidate.selected,
                    payload_json=payload,
                )
                self.session.add(existing)
            else:
                existing.disposition = candidate.disposition.value
                existing.eligibility_score = candidate.eligibility_score
                existing.strategy_score = candidate.strategy_score
                existing.complexity = candidate.complexity
                existing.rank = candidate.rank
                # Do not silently clear a previously authoritative selection
                # during a daily strategy refresh. Valuation/decision rebuilds
                # remain responsible for changing the winner.
                existing.selected = bool(existing.selected or candidate.selected)
                payload["selected"] = existing.selected
                if existing.selected:
                    payload["disposition"] = existing.disposition
                existing.payload_json = payload

    def save_strategy_evaluations(self, candidates: list[StrategyCandidate]) -> None:
        """Persist a complete evaluation set, even when every strategy is rejected."""
        self.policy.validate_strategy_evaluations(candidates)
        self._merge_strategy_candidates(candidates)

    def save_strategy_candidates(self, candidates: list[StrategyCandidate]) -> None:
        """Persist an actionable set that contains at least one eligible strategy."""
        self.policy.validate_strategy_candidates(candidates)
        self._merge_strategy_candidates(candidates)

    def save_strategy_comparison(self, comparison: StrategyComparison) -> None:
        # There is exactly one canonical comparison per opportunity. Rebuilds
        # update that singleton rather than inserting a new primary-key row.
        existing = self.session.query(StrategyComparisonModel).filter_by(
            opportunity_id=comparison.opportunity_id
        ).one_or_none()
        comparison_id = existing.comparison_id if existing else comparison.comparison_id
        payload = serialize_domain(comparison)
        payload["comparison_id"] = comparison_id
        self.session.merge(StrategyComparisonModel(
            comparison_id=comparison_id,
            opportunity_id=comparison.opportunity_id,
            selected_strategy_candidate_id=comparison.selected_strategy_candidate_id,
            policy_version=comparison.comparison_policy_version,
            created_at=comparison.created_at,
            payload_json=payload,
        ))

    def save_contract_recommendation(self, recommendation: ContractRecommendation) -> None:
        self.policy.validate_contract_recommendation(recommendation)
        # One canonical recommendation is retained for a strategy within an
        # option snapshot. Reprocessing that snapshot refreshes the row instead
        # of multiplying recommendations on every ingestion run.
        existing = self.session.query(ContractRecommendationModel).filter_by(
            opportunity_id=recommendation.opportunity_id,
            strategy_candidate_id=recommendation.strategy_candidate_id,
            option_snapshot_id=recommendation.option_snapshot_id,
        ).order_by(ContractRecommendationModel.created_at.desc()).first()
        recommendation_id = (
            existing.contract_recommendation_id
            if existing is not None
            else recommendation.contract_recommendation_id
        )
        payload = serialize_domain(recommendation)
        payload["contract_recommendation_id"] = recommendation_id
        if existing is None:
            self.session.add(ContractRecommendationModel(
                contract_recommendation_id=recommendation_id,
                opportunity_id=recommendation.opportunity_id,
                strategy_candidate_id=recommendation.strategy_candidate_id,
                option_snapshot_id=recommendation.option_snapshot_id,
                executable=recommendation.executable,
                liquidity_score=recommendation.liquidity_score,
                created_at=recommendation.created_at,
                payload_json=payload,
            ))
        else:
            existing.executable = recommendation.executable
            existing.liquidity_score = recommendation.liquidity_score
            existing.created_at = recommendation.created_at
            existing.payload_json = payload

    def save_execution_recommendation(self, recommendation: ExecutionRecommendation) -> None:
        existing = self.session.query(ExecutionRecommendationModel).filter_by(
            opportunity_id=recommendation.opportunity_id
        ).one_or_none()
        recommendation_id = (
            existing.execution_recommendation_id
            if existing else recommendation.execution_recommendation_id
        )
        payload = serialize_domain(recommendation)
        payload["execution_recommendation_id"] = recommendation_id
        self.session.merge(ExecutionRecommendationModel(
            execution_recommendation_id=recommendation_id,
            opportunity_id=recommendation.opportunity_id,
            strategy_candidate_id=recommendation.strategy_candidate_id,
            contract_recommendation_id=recommendation.contract_recommendation_id,
            underlying_stop=recommendation.underlying_stop,
            trailing_policy=recommendation.trailing_policy,
            ready_for_trade_builder=recommendation.ready_for_trade_builder,
            created_at=recommendation.created_at,
            payload_json=payload,
        ))


    def save_strategy_valuation(self, valuation_id: str, candidate: StrategyCandidate) -> None:
        existing = self.session.query(StrategyValuationModel).filter_by(
            opportunity_id=candidate.opportunity_id,
            strategy_candidate_id=candidate.strategy_candidate_id,
        ).one_or_none()
        canonical_valuation_id = existing.valuation_id if existing else valuation_id
        self.session.merge(StrategyValuationModel(
            valuation_id=canonical_valuation_id,
            opportunity_id=candidate.opportunity_id,
            strategy_candidate_id=candidate.strategy_candidate_id,
            strategy_score=float(candidate.strategy_score or 0.0),
            calibrated_probability=None if candidate.probability is None else candidate.probability.calibrated_probability,
            expected_value=candidate.expected_value,
            expected_return_on_risk=candidate.expected_return_on_risk,
            selected=candidate.selected,
            created_at=datetime.now(timezone.utc).isoformat(),
            payload_json=serialize_domain(candidate),
        ))

    def save_management_snapshot(self, snapshot) -> None:
        existing = self.session.query(PositionManagementSnapshotModel).filter_by(
            opportunity_id=snapshot.opportunity_id,
            strategy_candidate_id=snapshot.strategy_candidate_id,
        ).order_by(PositionManagementSnapshotModel.created_at.desc()).first()
        management_snapshot_id = (
            existing.management_snapshot_id if existing else snapshot.management_snapshot_id
        )
        payload = serialize_domain(snapshot)
        payload["management_snapshot_id"] = management_snapshot_id
        self.session.merge(PositionManagementSnapshotModel(
            management_snapshot_id=management_snapshot_id,
            opportunity_id=snapshot.opportunity_id,
            strategy_candidate_id=snapshot.strategy_candidate_id,
            thesis_integrity=snapshot.thesis_integrity,
            position_health=snapshot.position_health,
            action=snapshot.action,
            trailing_policy=snapshot.trailing_policy,
            created_at=datetime.now(timezone.utc).isoformat(),
            payload_json=payload,
        ))

    def save_outcome(self, attribution: OpportunityOutcomeAttribution) -> None:
        self.session.merge(OpportunityOutcomeAttributionModel(
            attribution_id=attribution.attribution_id,
            opportunity_id=attribution.opportunity_id,
            strategy_candidate_id=attribution.strategy_candidate_id,
            contract_recommendation_id=attribution.contract_recommendation_id,
            outcome=attribution.outcome,
            realized_return_pct=attribution.realized_return_pct,
            exit_reason=attribution.exit_reason,
            payload_json=serialize_domain(attribution),
        ))

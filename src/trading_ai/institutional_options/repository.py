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
    StrategyDisposition,
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
from .trade_builder_authority import classify_trade_builder_authority


class InstitutionalOpportunityRepository:
    def __init__(self, session: Session, policy: OpportunityGovernancePolicy | None = None) -> None:
        self.session = session
        self.policy = policy or OpportunityGovernancePolicy()

    def save_opportunity(self, opportunity: InstitutionalOpportunity, thesis: OpportunityThesis) -> None:
        """Persist the current governed source snapshot without losing continuity.

        M76.2.3 deliberately updates an already-loaded opportunity row in place.
        ``Session.merge`` is valid SQLAlchemy, but the ingestion service already holds
        the authoritative continuity row in the identity map; mutating that row makes
        the source-publication/decision-snapshot refresh explicit and eliminates any
        ambiguity about stale payload projection for READY_FOR_EXECUTION records.
        """
        self.policy.validate_opportunity(opportunity, thesis)
        lineage = opportunity.lineage
        values = dict(
            symbol=opportunity.symbol, asset_class=opportunity.asset_class, state=opportunity.state.value,
            direction=opportunity.direction.value, category=opportunity.category, overall_score=opportunity.overall_score,
            confidence=opportunity.confidence, conviction=opportunity.conviction, thesis_id=opportunity.thesis_id,
            stock_publication_name=lineage.stock_publication_name, stock_scanner_run_id=lineage.stock_scanner_run_id,
            stock_candidate_id=lineage.stock_candidate_id, stock_state_hash=lineage.stock_state_hash,
            option_snapshot_id=lineage.option_snapshot_id, version=opportunity.version, created_at=opportunity.created_at,
            updated_at=opportunity.updated_at, payload_json=serialize_domain(opportunity),
        )
        row = self.session.get(InstitutionalOpportunityModel, opportunity.opportunity_id)
        if row is None:
            row = InstitutionalOpportunityModel(opportunity_id=opportunity.opportunity_id, **values)
        else:
            for key, value in values.items():
                setattr(row, key, value)
        self.session.add(row)

        thesis_values = dict(
            opportunity_id=thesis.opportunity_id, direction=thesis.direction.value, setup_category=thesis.setup_category,
            primary_timeframe=thesis.primary_timeframe, invalidation_level=thesis.invalidation_level,
            entry_zone_low=thesis.entry_zone_low, entry_zone_high=thesis.entry_zone_high, created_at=thesis.created_at,
            payload_json=serialize_domain(thesis),
        )
        thesis_row = self.session.get(OpportunityThesisModel, thesis.thesis_id)
        if thesis_row is None:
            thesis_row = OpportunityThesisModel(thesis_id=thesis.thesis_id, **thesis_values)
        else:
            for key, value in thesis_values.items():
                setattr(thesis_row, key, value)
        self.session.add(thesis_row)

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

    def resolve_contract_regeneration_unavailable(
        self,
        opportunity_id: str,
        *,
        reason: str,
    ) -> InstitutionalOpportunityModel:
        """Close an expected regeneration attempt without restoring readiness.

        A current chain can legitimately contain no executable package for the
        selected strategy. That is a governed non-actionable outcome, not an
        unexpected recovery failure and never a reason to reuse stale lineage.
        The opportunity remains at ``STRATEGIES_GENERATED`` so a later source
        or options refresh may evaluate it again.
        """

        self.session.flush()
        row = self.session.get(InstitutionalOpportunityModel, opportunity_id)
        if row is None:
            raise LookupError(
                f"Institutional Opportunity not found: {opportunity_id}"
            )
        if row.state != OpportunityState.STRATEGIES_GENERATED.value:
            return row

        row.option_snapshot_id = None
        row.version += 1
        row.updated_at = datetime.now(timezone.utc).isoformat()
        payload_json = dict(row.payload_json or {})
        payload_json["state"] = OpportunityState.STRATEGIES_GENERATED.value
        lineage = dict(payload_json.get("lineage") or {})
        lineage["contract_option_snapshot_id"] = None
        lineage["option_snapshot_id"] = None
        payload_json["lineage"] = lineage

        metadata = dict(payload_json.get("metadata") or {})
        metadata["contract_option_snapshot_id"] = None
        metadata["m68_2_1_3_contract_option_snapshot_id"] = None
        metadata["execution_disposition"] = (
            "NO_EXECUTABLE_CURRENT_CONTRACT"
        )
        metadata["m68_2_1_3_contract_regeneration_required"] = False
        metadata["m68_2_1_3_contract_regeneration_status"] = (
            "GOVERNED_UNAVAILABLE"
        )
        metadata["m68_2_1_3_contract_lineage_reason"] = reason
        payload_json["metadata"] = metadata
        row.payload_json = payload_json

        execution = (
            self.session.query(ExecutionRecommendationModel)
            .filter_by(opportunity_id=opportunity_id)
            .one_or_none()
        )
        if execution is not None:
            execution_payload = dict(execution.payload_json or {})
            execution_payload["trade_plan_certification"] = {
                "status": "INVALIDATED",
                "certification_scope": (
                    "INSTITUTIONAL_OPTIONS_FINAL_PLAN"
                ),
                "version": "M68.2.1.3-CONTRACT-LINEAGE-1.0",
                "failure_codes": ["TPC-LIN-022"],
                "failure_reasons": [reason],
                "execution_disposition": (
                    "NO_EXECUTABLE_CURRENT_CONTRACT"
                ),
            }
            execution.ready_for_trade_builder = False
            execution.payload_json = execution_payload

        self.session.add(InstitutionalOpportunityAuditModel(
            audit_id=f"m62-audit-{uuid4().hex}",
            opportunity_id=opportunity_id,
            previous_state=OpportunityState.STRATEGIES_GENERATED.value,
            new_state=OpportunityState.STRATEGIES_GENERATED.value,
            actor="m68.2.1.3-contract-lineage-governance",
            reason=reason,
            event_timestamp=row.updated_at,
            payload_json={
                "version": row.version,
                "certification_code": "TPC-LIN-022",
                "execution_disposition": (
                    "NO_EXECUTABLE_CURRENT_CONTRACT"
                ),
            },
        ))
        return row

    def invalidate_ready_for_execution(self, opportunity_id: str, *, actor: str, reason: str, payload: dict | None = None) -> InstitutionalOpportunityModel:
        """Governed backward transition used only when downstream certification invalidates readiness."""
        self.session.flush()
        row = self.session.get(InstitutionalOpportunityModel, opportunity_id)
        if row is None:
            raise LookupError(f"Institutional Opportunity not found: {opportunity_id}")
        current = OpportunityState(row.state)
        if current != OpportunityState.READY_FOR_EXECUTION:
            return row
        row.state = OpportunityState.CONTRACTS_OPTIMIZED.value
        row.version += 1
        row.updated_at = datetime.now(timezone.utc).isoformat()
        execution = (
            self.session.query(ExecutionRecommendationModel)
            .filter_by(opportunity_id=opportunity_id)
            .one_or_none()
        )
        if execution is not None:
            execution.ready_for_trade_builder = False
            execution_payload = dict(execution.payload_json or {})
            certification = dict(
                execution_payload.get("trade_plan_certification") or {}
            )
            if certification:
                entry_execution = dict(
                    certification.get("entry_execution") or {}
                )
                entry_reasons = list(
                    entry_execution.get("reason_codes") or ()
                )
                entry_reasons.append("LIFECYCLE_READINESS_INVALIDATED")
                entry_execution["reason_codes"] = list(
                    dict.fromkeys(entry_reasons)
                )
                certification["execution_disposition"] = "INVALIDATED"
                certification["trade_builder_ready"] = False
                certification["entry_execution"] = entry_execution
                execution_payload["trade_plan_certification"] = certification
            execution_payload["trade_builder_authority"] = {
                "version": (
                    "M68.2.1.15-CERTIFIED-TRADE-BUILDER-AUTHORITY-1.0"
                ),
                "authorized": False,
                "reason_codes": ["LIFECYCLE_READINESS_INVALIDATED"],
                "invalidation_reason": reason,
            }
            execution.payload_json = execution_payload
        event_payload = {"version": row.version, "m75_2_2_readiness_invalidated": True}
        event_payload.update(dict(payload or {}))
        self.session.add(InstitutionalOpportunityAuditModel(
            audit_id=f"m62-audit-{uuid4().hex}",
            opportunity_id=opportunity_id,
            previous_state=current.value,
            new_state=OpportunityState.CONTRACTS_OPTIMIZED.value,
            actor=actor,
            reason=reason,
            event_timestamp=row.updated_at,
            payload_json=event_payload,
        ))
        return row

    def reset_for_contract_regeneration(
        self,
        opportunity_id: str,
        *,
        expected_option_snapshot_id: str | None,
        available_option_snapshot_ids: tuple[str, ...] = (),
        reason: str,
    ) -> InstitutionalOpportunityModel:
        """Fail closed when READY/optimized lineage has no exact contract.

        Strategy selection remains valid, so the governed recovery point is
        ``STRATEGIES_GENERATED`` rather than a full return to ``VALIDATED``.
        The contract optimizer can then publish a current exact Polygon package
        before certification is attempted again.
        """

        self.session.flush()
        row = self.session.get(InstitutionalOpportunityModel, opportunity_id)
        if row is None:
            raise LookupError(
                f"Institutional Opportunity not found: {opportunity_id}"
            )
        current = OpportunityState(row.state)
        if current not in {
            OpportunityState.CONTRACTS_OPTIMIZED,
            OpportunityState.READY_FOR_EXECUTION,
        }:
            return row

        previous = current
        row.state = OpportunityState.STRATEGIES_GENERATED.value
        row.option_snapshot_id = None
        row.version += 1
        row.updated_at = datetime.now(timezone.utc).isoformat()

        payload_json = dict(row.payload_json or {})
        payload_json["state"] = OpportunityState.STRATEGIES_GENERATED.value
        lineage = dict(payload_json.get("lineage") or {})
        metadata = dict(payload_json.get("metadata") or {})
        source_snapshot_id = (
            lineage.get("source_option_snapshot_id")
            or metadata.get("source_option_snapshot_id")
            or metadata.get("m68_2_1_3_source_option_snapshot_id")
            or expected_option_snapshot_id
        )
        lineage["source_option_snapshot_id"] = source_snapshot_id
        lineage["contract_option_snapshot_id"] = None
        lineage["option_snapshot_id"] = None
        payload_json["lineage"] = lineage

        metadata["source_option_snapshot_id"] = source_snapshot_id
        metadata["contract_option_snapshot_id"] = None
        metadata["m68_2_1_3_contract_option_snapshot_id"] = None
        metadata["execution_disposition"] = "REGENERATE_REQUIRED"
        metadata["m68_2_1_3_contract_regeneration_required"] = True
        metadata["m68_2_1_3_contract_lineage_reason"] = reason
        metadata["m68_2_1_3_expected_option_snapshot_id"] = (
            expected_option_snapshot_id
        )
        metadata["m68_2_1_3_available_option_snapshot_ids"] = list(
            available_option_snapshot_ids
        )
        metadata.pop("institutional_plan_certification", None)
        metadata.pop("institutional_plan_fingerprint", None)
        payload_json["metadata"] = metadata
        row.payload_json = payload_json

        execution = (
            self.session.query(ExecutionRecommendationModel)
            .filter_by(opportunity_id=opportunity_id)
            .one_or_none()
        )
        if execution is not None:
            execution_payload = dict(execution.payload_json or {})
            prior = dict(
                execution_payload.get("trade_plan_certification") or {}
            )
            if prior:
                execution_payload["prior_trade_plan_certification"] = prior
            execution_payload["trade_plan_certification"] = {
                "status": "INVALIDATED",
                "certification_scope": "INSTITUTIONAL_OPTIONS_FINAL_PLAN",
                "version": "M68.2.1.3-CONTRACT-LINEAGE-1.0",
                "failure_codes": ["TPC-LIN-021"],
                "failure_reasons": [reason],
                "execution_disposition": "REGENERATE_REQUIRED",
                "expected_option_snapshot_id": expected_option_snapshot_id,
                "available_option_snapshot_ids": list(
                    available_option_snapshot_ids
                ),
            }
            execution.ready_for_trade_builder = False
            execution.payload_json = execution_payload

        self.session.add(InstitutionalOpportunityAuditModel(
            audit_id=f"m62-audit-{uuid4().hex}",
            opportunity_id=opportunity_id,
            previous_state=previous.value,
            new_state=OpportunityState.STRATEGIES_GENERATED.value,
            actor="m68.2.1.3-contract-lineage-governance",
            reason=reason,
            event_timestamp=row.updated_at,
            payload_json={
                "version": row.version,
                "certification_code": "TPC-LIN-021",
                "execution_disposition": "REGENERATE_REQUIRED",
                "expected_option_snapshot_id": expected_option_snapshot_id,
                "available_option_snapshot_ids": list(
                    available_option_snapshot_ids
                ),
            },
        ))
        return row


    def reset_for_source_plan_change(self, opportunity_id: str, *, actor: str, old_fingerprint: str, new_fingerprint: str) -> InstitutionalOpportunityModel:
        """Invalidate pre-execution Institutional Options work when the source scanner plan changes."""
        self.session.flush()
        row = self.session.get(InstitutionalOpportunityModel, opportunity_id)
        if row is None:
            raise LookupError(f"Institutional Opportunity not found: {opportunity_id}")
        current = OpportunityState(row.state)
        resettable = {
            OpportunityState.DISCOVERED, OpportunityState.VALIDATED, OpportunityState.STRATEGIES_GENERATED,
            OpportunityState.CONTRACTS_OPTIMIZED, OpportunityState.READY_FOR_EXECUTION,
        }
        if current not in resettable:
            return row
        previous = current
        row.state = OpportunityState.VALIDATED.value
        row.version += 1
        row.updated_at = datetime.now(timezone.utc).isoformat()
        payload_json = dict(row.payload_json or {})
        payload_json["state"] = OpportunityState.VALIDATED.value
        metadata = dict(payload_json.get("metadata") or {})
        metadata["m75_2_2_source_plan_changed"] = True
        metadata["previous_source_plan_fingerprint"] = old_fingerprint
        metadata["source_plan_fingerprint"] = new_fingerprint
        metadata.pop("institutional_plan_certification", None)
        metadata.pop("institutional_plan_fingerprint", None)
        metadata["m75_2_2_final_plan_certification_pending"] = True
        payload_json["metadata"] = metadata
        row.payload_json = payload_json
        execution = self.session.query(ExecutionRecommendationModel).filter_by(opportunity_id=opportunity_id).one_or_none()
        if execution is not None:
            ep = dict(execution.payload_json or {})
            prior = dict(ep.get("trade_plan_certification") or {})
            if prior:
                ep["prior_trade_plan_certification"] = prior
            ep["trade_plan_certification"] = {
                "status": "INVALIDATED",
                "certification_scope": "INSTITUTIONAL_OPTIONS_FINAL_PLAN",
                "version": "M75.2-ITPCE-LINEAGE-1.1",
                "failure_codes": ["TPC-LIN-020"],
                "failure_reasons": ["Source Stock Intelligence trade plan fingerprint changed; regenerate Institutional Options plan."],
                "source_plan_fingerprint": new_fingerprint,
                "previous_source_plan_fingerprint": old_fingerprint,
            }
            execution.ready_for_trade_builder = False
            execution.payload_json = ep
        self.session.add(InstitutionalOpportunityAuditModel(
            audit_id=f"m62-audit-{uuid4().hex}",
            opportunity_id=opportunity_id,
            previous_state=previous.value,
            new_state=OpportunityState.VALIDATED.value,
            actor=actor,
            reason="M75.2.2 source Stock Intelligence trade plan changed; downstream readiness invalidated",
            event_timestamp=row.updated_at,
            payload_json={
                "version": row.version,
                "old_plan_fingerprint": old_fingerprint,
                "new_plan_fingerprint": new_fingerprint,
                "certification_code": "TPC-LIN-020",
            },
        ))
        return row


    def _merge_strategy_candidates(self, candidates: list[StrategyCandidate]) -> None:
        """Upsert strategy evaluations by their database natural key.

        Strategy identifiers are generated for new evaluations, while the table
        enforces one row per ``(opportunity_id, strategy)``. Daily rebuilds must
        therefore preserve the existing identifier and refresh the row rather
        than attempting a second insert with a new primary key. Selection is a
        current valuation result, not an append-only fact: every rebuild must
        replace the prior flag exactly so only the current comparison winner is
        authoritative.
        """
        opportunity_ids = tuple(
            sorted({str(candidate.opportunity_id) for candidate in candidates})
        )
        if opportunity_ids:
            prior_rows = (
                self.session.query(StrategyCandidateModel)
                .filter(StrategyCandidateModel.opportunity_id.in_(opportunity_ids))
                .all()
            )
            for prior in prior_rows:
                prior.selected = False
                prior_payload = dict(prior.payload_json or {})
                prior_payload["selected"] = False
                if prior.disposition == StrategyDisposition.SELECTED.value:
                    prior.disposition = StrategyDisposition.ELIGIBLE.value
                    prior_payload["disposition"] = StrategyDisposition.ELIGIBLE.value
                prior.payload_json = prior_payload

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
                existing.selected = bool(candidate.selected)
                payload["selected"] = existing.selected
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
        # Contract optimization evaluates every eligible strategy against exact
        # market packages before valuation.  Valuation legitimately replaces
        # the final selected strategy, but it must not erase that exhaustive
        # feasibility proof from the canonical comparison row.
        if existing is not None:
            contract_authority = dict(
                (existing.payload_json or {}).get(
                    "contract_feasibility_authority"
                )
                or {}
            )
            if contract_authority:
                contract_authority[
                    "current_selected_strategy_candidate_id"
                ] = comparison.selected_strategy_candidate_id
                contract_authority["current_selection_policy_version"] = (
                    comparison.comparison_policy_version
                )
                payload["contract_feasibility_authority"] = (
                    contract_authority
                )
        self.session.merge(StrategyComparisonModel(
            comparison_id=comparison_id,
            opportunity_id=comparison.opportunity_id,
            selected_strategy_candidate_id=comparison.selected_strategy_candidate_id,
            policy_version=comparison.comparison_policy_version,
            created_at=comparison.created_at,
            payload_json=payload,
        ))

    def save_contract_recommendation(
        self, recommendation: ContractRecommendation
    ) -> str:
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
        return str(recommendation_id)

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
        authority = classify_trade_builder_authority(
            payload,
            recommendation.ready_for_trade_builder,
        )
        if authority["column_consistent"] is not True:
            raise ValueError(
                "Execution readiness disagrees with final certification: "
                + ",".join(authority["reason_codes"])
            )
        payload["trade_builder_authority"] = authority
        self.session.merge(ExecutionRecommendationModel(
            execution_recommendation_id=recommendation_id,
            opportunity_id=recommendation.opportunity_id,
            strategy_candidate_id=recommendation.strategy_candidate_id,
            contract_recommendation_id=recommendation.contract_recommendation_id,
            underlying_stop=recommendation.underlying_stop,
            trailing_policy=recommendation.trailing_policy,
            ready_for_trade_builder=authority["authorized"],
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

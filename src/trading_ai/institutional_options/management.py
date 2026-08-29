from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable
from uuid import uuid4

from sqlalchemy.orm import Session

from .domain import ExecutionRecommendation, OpportunityState, OpportunityThesis, StrategyCandidate, StrategyDisposition, ProbabilityDecomposition, ThesisDirection
from .models import (
    ContractRecommendationModel,
    InstitutionalOpportunityModel,
    OpportunityThesisModel,
    StrategyCandidateModel,
    StrategyComparisonModel,
)
from .repository import InstitutionalOpportunityRepository
from trading_ai.trade_plan_certification import certify_institutional_underlying_plan
from trading_ai.stock_intelligence.models import StockScannerCandidateModel


@dataclass(frozen=True)
class DynamicManagementPolicy:
    emergency_option_stop_pct: float = 0.55
    minimum_partial_profit_pct: float = 0.25
    partial_profit_fraction: float = 0.33
    theta_exit_days_long_premium: int = 10
    theta_exit_days_spreads: int = 5
    thesis_reduce_threshold: float = 0.62
    thesis_exit_threshold: float = 0.40
    policy_version: str = "M62-PH6-1.0"


@dataclass(frozen=True)
class PositionManagementSnapshot:
    management_snapshot_id: str
    opportunity_id: str
    strategy_candidate_id: str
    thesis_integrity: float
    position_health: float
    action: str
    partial_profit_fraction: float
    trailing_policy: str
    underlying_stop: float
    underlying_targets: tuple[float, ...]
    emergency_option_stop_pct: float
    theta_exit_days_to_expiry: int
    volatility_exit_rule: str
    liquidity_exit_rule: str
    assignment_risk_rule: str
    evidence: tuple[str, ...]
    warnings: tuple[str, ...]
    policy_version: str


@dataclass(frozen=True)
class DynamicManagementResult:
    requested: int
    created: int
    failed: int
    certified: int = 0
    rejected: int = 0
    waiting_for_entry: int = 0
    regenerate_required: int = 0
    contract_regeneration_required: int = 0
    contract_regeneration_opportunity_ids: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


class ContractLineageRegenerationRequired(ValueError):
    """Expected fail-closed disposition for missing exact contract lineage."""

    def __init__(
        self,
        *,
        expected_option_snapshot_id: str | None,
        available_option_snapshot_ids: tuple[str, ...],
    ) -> None:
        self.expected_option_snapshot_id = expected_option_snapshot_id
        self.available_option_snapshot_ids = available_option_snapshot_ids
        expected = expected_option_snapshot_id or "MISSING"
        available = ", ".join(available_option_snapshot_ids) or "NONE"
        super().__init__(
            "No executable contract recommendation exists for the current "
            f"option snapshot; expected={expected}; available={available}"
        )


class UnderlyingDrivenManagementEngine:
    def __init__(self, policy: DynamicManagementPolicy | None = None) -> None:
        self.policy = policy or DynamicManagementPolicy()

    def build(self, thesis: OpportunityThesis, strategy: StrategyCandidate) -> tuple[ExecutionRecommendation, PositionManagementSnapshot]:
        entry_mid = (thesis.entry_zone_low + thesis.entry_zone_high) / 2.0
        ordered_targets = tuple(sorted(set(thesis.targets), reverse=thesis.direction.value == "BEARISH"))
        if not ordered_targets:
            raise ValueError("At least one dynamic underlying target is required")
        stop_distance = abs(entry_mid - thesis.invalidation_level)
        first_target_distance = abs(ordered_targets[0] - entry_mid)
        rr = first_target_distance / max(stop_distance, 1e-9)
        probability = strategy.probability.calibrated_probability if strategy.probability else 0.5
        thesis_integrity = max(0.0, min(1.0, 0.55 * probability + 0.20 * min(rr / 3.0, 1.0) + 0.25 * min(strategy.eligibility_score / 100.0, 1.0)))
        liquidity = float(strategy.metadata.get("liquidity_score", 50.0))
        position_health = max(0.0, min(1.0, thesis_integrity * 0.75 + min(liquidity / 100.0, 1.0) * 0.25))
        if thesis_integrity < self.policy.thesis_exit_threshold:
            action = "EXIT"
        elif thesis_integrity < self.policy.thesis_reduce_threshold:
            action = "REDUCE"
        elif rr >= 2.0 and probability >= 0.60:
            action = "HOLD_AND_TRAIL"
        else:
            action = "HOLD"

        trailing = "UNDERLYING_HIGHER_LOW" if thesis.direction.value == "BULLISH" else "UNDERLYING_LOWER_HIGH"
        if "SIDEWAYS" in thesis.structure_state.upper() or "COMPRESSION" in thesis.structure_state.upper():
            trailing = "INSTITUTIONAL_STRUCTURE_ZONE"
        theta_days = self.policy.theta_exit_days_long_premium if strategy.strategy in {"LONG_CALL", "LONG_PUT"} else self.policy.theta_exit_days_spreads
        execution = ExecutionRecommendation(
            execution_recommendation_id=f"m62-execution-{uuid4().hex}",
            opportunity_id=thesis.opportunity_id,
            strategy_candidate_id=strategy.strategy_candidate_id,
            contract_recommendation_id=str(strategy.metadata.get("contract_recommendation_id") or ""),
            underlying_entry_zone_low=thesis.entry_zone_low,
            underlying_entry_zone_high=thesis.entry_zone_high,
            underlying_stop=thesis.invalidation_level,
            underlying_targets=ordered_targets,
            trailing_policy=trailing,
            emergency_option_stop_pct=self.policy.emergency_option_stop_pct,
            theta_exit_days_to_expiry=theta_days,
            volatility_exit_rule="EXIT_OR_REDUCE_ON_IV_COLLAPSE_WITH_THESIS_DETERIORATION",
            invalidation_reasons=("UNDERLYING_STRUCTURE_INVALIDATED", "THESIS_INTEGRITY_BELOW_THRESHOLD"),
            ready_for_trade_builder=bool(strategy.selected),
        )
        snapshot = PositionManagementSnapshot(
            management_snapshot_id=f"m62-management-{uuid4().hex}",
            opportunity_id=thesis.opportunity_id,
            strategy_candidate_id=strategy.strategy_candidate_id,
            thesis_integrity=round(thesis_integrity, 6),
            position_health=round(position_health, 6),
            action=action,
            partial_profit_fraction=self.policy.partial_profit_fraction if rr >= 1.5 else 0.0,
            trailing_policy=trailing,
            underlying_stop=thesis.invalidation_level,
            underlying_targets=ordered_targets,
            emergency_option_stop_pct=self.policy.emergency_option_stop_pct,
            theta_exit_days_to_expiry=theta_days,
            volatility_exit_rule="IV_COLLAPSE_AND_THESIS_DETERIORATION",
            liquidity_exit_rule="EXIT_IF_SPREAD_OR_DEPTH_BREACHES_EXECUTION_GOVERNANCE",
            assignment_risk_rule="EXIT_OR_ROLL_SHORT_LEGS_BEFORE_ASSIGNMENT_RISK_WINDOW",
            evidence=(
                f"Thesis integrity {thesis_integrity:.2%}",
                f"Position health {position_health:.2%}",
                f"Structural reward/risk {rr:.2f}",
                f"Selected trailing policy {trailing}",
            ),
            warnings=tuple(thesis.risks),
            policy_version=self.policy.policy_version,
        )
        return execution, snapshot


class InstitutionalDynamicManagementService:
    def __init__(self, session: Session, policy: DynamicManagementPolicy | None = None) -> None:
        self.session = session
        self.policy = policy or DynamicManagementPolicy()
        self.engine = UnderlyingDrivenManagementEngine(self.policy)
        self.repository = InstitutionalOpportunityRepository(session)

    def _authoritative_strategy_row(
        self,
        opportunity: InstitutionalOpportunityModel,
    ) -> StrategyCandidateModel:
        comparison = self.session.query(StrategyComparisonModel).filter_by(
            opportunity_id=opportunity.opportunity_id
        ).one_or_none()
        selected_id = None if comparison is None else comparison.selected_strategy_candidate_id
        if not selected_id:
            raise ValueError("Current strategy comparison has no selected strategy")
        strategy = self.session.get(StrategyCandidateModel, selected_id)
        if strategy is None or strategy.opportunity_id != opportunity.opportunity_id:
            raise ValueError(
                "Current strategy comparison references a missing or foreign strategy"
            )
        return strategy

    def _authoritative_contract_row(
        self,
        opportunity: InstitutionalOpportunityModel,
        strategy_candidate_id: str,
    ) -> ContractRecommendationModel:
        option_snapshot_id = str(opportunity.option_snapshot_id or "")
        available_snapshot_ids = tuple(sorted({
            str(snapshot_id)
            for (snapshot_id,) in (
                self.session.query(
                    ContractRecommendationModel.option_snapshot_id
                )
                .filter_by(
                    opportunity_id=opportunity.opportunity_id,
                    strategy_candidate_id=strategy_candidate_id,
                    executable=True,
                )
                .all()
            )
            if snapshot_id
        }))
        if not option_snapshot_id:
            raise ContractLineageRegenerationRequired(
                expected_option_snapshot_id=None,
                available_option_snapshot_ids=available_snapshot_ids,
            )
        contract = (
            self.session.query(ContractRecommendationModel)
            .filter_by(
                opportunity_id=opportunity.opportunity_id,
                strategy_candidate_id=strategy_candidate_id,
                option_snapshot_id=option_snapshot_id,
                executable=True,
            )
            .order_by(
                ContractRecommendationModel.liquidity_score.desc().nullslast(),
                ContractRecommendationModel.created_at.desc(),
                ContractRecommendationModel.contract_recommendation_id,
            )
            .first()
        )
        if contract is None:
            raise ContractLineageRegenerationRequired(
                expected_option_snapshot_id=option_snapshot_id,
                available_option_snapshot_ids=available_snapshot_ids,
            )
        return contract

    def generate(self, *, opportunity_ids: Iterable[str] | None = None, limit: int | None = None) -> DynamicManagementResult:
        query = self.session.query(InstitutionalOpportunityModel).filter(
            InstitutionalOpportunityModel.state.in_((
                OpportunityState.CONTRACTS_OPTIMIZED.value,
                OpportunityState.READY_FOR_EXECUTION.value,
            ))
        )
        if opportunity_ids:
            query = query.filter(InstitutionalOpportunityModel.opportunity_id.in_(tuple(opportunity_ids)))
        rows = query.order_by(InstitutionalOpportunityModel.overall_score.desc(), InstitutionalOpportunityModel.symbol)
        if limit is not None:
            rows = rows.limit(limit)
        opportunities = rows.all()
        created = failed = certified = rejected = waiting = regenerate = 0
        contract_regeneration_ids: list[str] = []
        errors: list[str] = []
        for row in opportunities:
            opportunity_id = str(row.opportunity_id)
            try:
                with self.session.begin_nested():
                    thesis_row = self.session.query(OpportunityThesisModel).filter_by(opportunity_id=row.opportunity_id).one()
                    thesis_payload = dict(thesis_row.payload_json or {})
                    thesis = OpportunityThesis(**(thesis_payload | {"direction": ThesisDirection(thesis_payload["direction"]), "targets": tuple(thesis_payload.get("targets") or ()), "evidence": tuple(thesis_payload.get("evidence") or ()), "risks": tuple(thesis_payload.get("risks") or ())}))
                    strategy_row = self._authoritative_strategy_row(row)
                    strategy_payload = dict(strategy_row.payload_json or {})
                    probability_payload = strategy_payload.get("probability")
                    strategy = StrategyCandidate(**(strategy_payload | {"disposition": StrategyDisposition(strategy_payload["disposition"]), "probability": None if not probability_payload else ProbabilityDecomposition(**probability_payload), "accepted_reasons": tuple(strategy_payload.get("accepted_reasons") or ()), "rejection_reasons": tuple(strategy_payload.get("rejection_reasons") or ())}))
                    contract_row = self._authoritative_contract_row(
                        row,
                        strategy.strategy_candidate_id,
                    )
                    strategy = StrategyCandidate(**(strategy.__dict__ | {"metadata": dict(strategy.metadata) | {"contract_recommendation_id": contract_row.contract_recommendation_id}}))
                    execution, snapshot = self.engine.build(thesis, strategy)
                    opportunity_payload = dict(row.payload_json or {})
                    stock_certification = dict((opportunity_payload.get("metadata") or {}).get("trade_plan_certification") or {})
                    source_candidate = self.session.get(
                        StockScannerCandidateModel,
                        str(row.stock_candidate_id or ""),
                    )
                    source_candidate_payload = (
                        {} if source_candidate is None
                        else dict(source_candidate.payload_json or {})
                    )
                    source_trade_plan = dict(
                        source_candidate_payload.get("trade_plan") or {}
                    )
                    entry_policy = dict(source_trade_plan.get("entry") or {})
                    geometry_context = dict(
                        source_trade_plan.get("geometry_context") or {}
                    )
                    contract_payload = dict(contract_row.payload_json or {})
                    legs = list(contract_payload.get("legs") or [])
                    dynamic_management = {
                        "underlying_entry_zone_low": thesis.entry_zone_low,
                        "underlying_entry_zone_high": thesis.entry_zone_high,
                        "underlying_stop": execution.underlying_stop,
                        "underlying_targets": list(execution.underlying_targets),
                        "trailing_policy": execution.trailing_policy,
                        "emergency_option_stop_pct": execution.emergency_option_stop_pct,
                        "theta_exit_days_to_expiry": execution.theta_exit_days_to_expiry,
                        "volatility_exit_rule": execution.volatility_exit_rule,
                        "assignment_risk_rule": snapshot.assignment_risk_rule,
                        "management_mode": "PLATFORM_MANAGED_AFTER_FILL",
                    }
                    certification = certify_institutional_underlying_plan(
                        stock_certification=stock_certification,
                        direction=thesis.direction.value,
                        entry_zone_low=thesis.entry_zone_low,
                        entry_zone_high=thesis.entry_zone_high,
                        structural_stop=execution.underlying_stop,
                        targets=execution.underlying_targets,
                        strategy=strategy.strategy,
                        legs=legs,
                        contract_executable=bool(contract_row.executable),
                        dynamic_management=dynamic_management,
                        entry_policy=entry_policy,
                        geometry_context=geometry_context,
                    )
                    execution = replace(
                        execution,
                        ready_for_trade_builder=(
                            certification.get("trade_builder_ready") is True
                        ),
                        trade_plan_certification=certification,
                    )
                    self.repository.save_execution_recommendation(execution)
                    self.repository.save_management_snapshot(snapshot)
                    opportunity_lineage = dict(
                        opportunity_payload.get("lineage") or {}
                    )
                    opportunity_lineage["contract_option_snapshot_id"] = (
                        contract_row.option_snapshot_id
                    )
                    opportunity_lineage["option_snapshot_id"] = (
                        contract_row.option_snapshot_id
                    )
                    opportunity_payload["lineage"] = opportunity_lineage
                    metadata = dict(opportunity_payload.get("metadata") or {})
                    metadata["institutional_plan_certification"] = certification
                    metadata["institutional_plan_fingerprint"] = certification.get("plan_fingerprint")
                    metadata["source_plan_fingerprint"] = certification.get("source_plan_fingerprint")
                    metadata["institutional_plan_mutated"] = bool(certification.get("plan_mutated"))
                    metadata["execution_disposition"] = certification.get(
                        "execution_disposition"
                    )
                    metadata["entry_execution"] = certification.get(
                        "entry_execution"
                    )
                    metadata["m68_2_1_3_contract_option_snapshot_id"] = (
                        contract_row.option_snapshot_id
                    )
                    metadata["contract_option_snapshot_id"] = (
                        contract_row.option_snapshot_id
                    )
                    for stale_key in (
                        "m68_2_1_3_contract_regeneration_required",
                        "m68_2_1_3_contract_lineage_reason",
                        "m68_2_1_3_expected_option_snapshot_id",
                        "m68_2_1_3_available_option_snapshot_ids",
                    ):
                        metadata.pop(stale_key, None)
                    opportunity_payload["metadata"] = metadata
                    row.payload_json = opportunity_payload
                    if (
                        certification.get("status") == "PASS"
                        and certification.get("trade_builder_ready") is True
                        and certification.get("execution_disposition") == "READY_NOW"
                    ):
                        certified += 1
                        if row.state == OpportunityState.CONTRACTS_OPTIMIZED.value:
                            self.repository.transition(
                                row.opportunity_id,
                                OpportunityState.READY_FOR_EXECUTION,
                                "m75.2.2-institutional-plan-certification",
                                "Final Institutional Options plan certified for Trade Builder handoff",
                            )
                    elif certification.get("status") == "PASS":
                        disposition = str(
                            certification.get("execution_disposition")
                            or "WAITING_FOR_ENTRY"
                        )
                        if disposition == "REGENERATE_REQUIRED":
                            regenerate += 1
                        else:
                            waiting += 1
                        if row.state == OpportunityState.READY_FOR_EXECUTION.value:
                            self.repository.invalidate_ready_for_execution(
                                row.opportunity_id,
                                actor="m68.2.1-conditional-entry-governance",
                                reason=(
                                    "Structurally certified plan is not actionable now; "
                                    f"execution disposition {disposition}"
                                ),
                                payload={
                                    "certification_id": certification.get("certification_id"),
                                    "execution_disposition": disposition,
                                    "entry_execution": certification.get("entry_execution") or {},
                                    "plan_fingerprint": certification.get("plan_fingerprint"),
                                },
                            )
                    else:
                        if row.state == OpportunityState.READY_FOR_EXECUTION.value:
                            self.repository.invalidate_ready_for_execution(
                                row.opportunity_id,
                                actor="m75.2.2-institutional-plan-certification",
                                reason="Final Institutional Options plan certification invalidated READY_FOR_EXECUTION",
                                payload={
                                    "certification_id": certification.get("certification_id"),
                                    "failure_codes": certification.get("failure_codes") or [],
                                    "plan_fingerprint": certification.get("plan_fingerprint"),
                                },
                            )
                        if row.state == OpportunityState.CONTRACTS_OPTIMIZED.value:
                            self.repository.transition(
                                row.opportunity_id,
                                OpportunityState.REJECTED,
                                "m75.2.2-institutional-plan-certification",
                                "Final Institutional Options plan failed certification: "
                                + ", ".join(
                                    certification.get("failure_codes")
                                    or ["UNSPECIFIED_CERTIFICATION_FAILURE"]
                                ),
                            )
                            rejected += 1
                    created += 1
            except ContractLineageRegenerationRequired as exc:
                try:
                    with self.session.begin_nested():
                        self.repository.reset_for_contract_regeneration(
                            opportunity_id,
                            expected_option_snapshot_id=(
                                exc.expected_option_snapshot_id
                            ),
                            available_option_snapshot_ids=(
                                exc.available_option_snapshot_ids
                            ),
                            reason=str(exc),
                        )
                    regenerate += 1
                    contract_regeneration_ids.append(opportunity_id)
                except Exception as reset_exc:
                    failed += 1
                    errors.append(
                        f"{opportunity_id}: {type(reset_exc).__name__}: "
                        f"{reset_exc}"
                    )
            except Exception as exc:
                failed += 1
                errors.append(f"{opportunity_id}: {type(exc).__name__}: {exc}")
        return DynamicManagementResult(
            requested=len(opportunities),
            created=created,
            failed=failed,
            certified=certified,
            rejected=rejected,
            waiting_for_entry=waiting,
            regenerate_required=regenerate,
            contract_regeneration_required=len(contract_regeneration_ids),
            contract_regeneration_opportunity_ids=tuple(
                contract_regeneration_ids
            ),
            errors=tuple(errors),
        )

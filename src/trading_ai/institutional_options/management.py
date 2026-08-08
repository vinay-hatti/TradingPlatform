from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import uuid4

from sqlalchemy.orm import Session

from .domain import ExecutionRecommendation, OpportunityState, OpportunityThesis, StrategyCandidate, StrategyDisposition, ProbabilityDecomposition, ThesisDirection
from .models import (
    ContractRecommendationModel,
    ExecutionRecommendationModel,
    InstitutionalOpportunityModel,
    OpportunityThesisModel,
    StrategyCandidateModel,
)
from .repository import InstitutionalOpportunityRepository


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
    errors: tuple[str, ...] = ()


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

    def generate(self, *, opportunity_ids: Iterable[str] | None = None, limit: int | None = None) -> DynamicManagementResult:
        query = self.session.query(InstitutionalOpportunityModel).filter(
            InstitutionalOpportunityModel.state == OpportunityState.READY_FOR_EXECUTION.value
        )
        if opportunity_ids:
            query = query.filter(InstitutionalOpportunityModel.opportunity_id.in_(tuple(opportunity_ids)))
        rows = query.order_by(InstitutionalOpportunityModel.overall_score.desc(), InstitutionalOpportunityModel.symbol)
        if limit is not None:
            rows = rows.limit(limit)
        opportunities = rows.all()
        created = failed = 0
        errors: list[str] = []
        for row in opportunities:
            opportunity_id = str(row.opportunity_id)
            try:
                with self.session.begin_nested():
                    thesis_row = self.session.query(OpportunityThesisModel).filter_by(opportunity_id=row.opportunity_id).one()
                    thesis_payload = dict(thesis_row.payload_json or {})
                    thesis = OpportunityThesis(**(thesis_payload | {"direction": ThesisDirection(thesis_payload["direction"]), "targets": tuple(thesis_payload.get("targets") or ()), "evidence": tuple(thesis_payload.get("evidence") or ()), "risks": tuple(thesis_payload.get("risks") or ())}))
                    strategy_row = self.session.query(StrategyCandidateModel).filter_by(opportunity_id=row.opportunity_id, selected=True).one()
                    strategy_payload = dict(strategy_row.payload_json or {})
                    probability_payload = strategy_payload.get("probability")
                    strategy = StrategyCandidate(**(strategy_payload | {"disposition": StrategyDisposition(strategy_payload["disposition"]), "probability": None if not probability_payload else ProbabilityDecomposition(**probability_payload), "accepted_reasons": tuple(strategy_payload.get("accepted_reasons") or ()), "rejection_reasons": tuple(strategy_payload.get("rejection_reasons") or ())}))
                    contract_row = self.session.query(ContractRecommendationModel).filter_by(
                        opportunity_id=row.opportunity_id,
                        strategy_candidate_id=strategy.strategy_candidate_id,
                    ).one()
                    strategy = StrategyCandidate(**(strategy.__dict__ | {"metadata": dict(strategy.metadata) | {"contract_recommendation_id": contract_row.contract_recommendation_id}}))
                    execution, snapshot = self.engine.build(thesis, strategy)
                    self.repository.save_execution_recommendation(execution)
                    self.repository.save_management_snapshot(snapshot)
                    created += 1
            except Exception as exc:
                failed += 1
                errors.append(f"{opportunity_id}: {type(exc).__name__}: {exc}")
        return DynamicManagementResult(len(opportunities), created, failed, tuple(errors))

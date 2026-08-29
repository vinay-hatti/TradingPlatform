from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from uuid import uuid4

from sqlalchemy import desc, inspect
from sqlalchemy.orm import Session

from .domain import OpportunityState, deterministic_hash
from .management import InstitutionalDynamicManagementService
from .models import (
    ContractRecommendationModel,
    ExecutionRecommendationModel,
    InstitutionalDecisionSnapshotModel,
    InstitutionalOpportunityModel,
    OpportunityThesisModel,
    PositionManagementSnapshotModel,
    StrategyCandidateModel,
    StrategyComparisonModel,
    StrategyValuationModel,
)
from .valuation import InstitutionalStrategyValuationService
from .repository import InstitutionalOpportunityRepository
from .trade_builder_authority import classify_trade_builder_authority

try:
    from trading_ai.portfolio_management.database_models import PortfolioSnapshotModel
except ImportError:  # pragma: no cover - optional portfolio subsystem
    PortfolioSnapshotModel = None


@dataclass(frozen=True)
class InstitutionalDecisionPolicy:
    minimum_institutional_score: float = 45.0
    policy_version: str = "M62-DECISION-1.0"


@dataclass(frozen=True)
class InstitutionalDecisionResult:
    requested: int
    created: int
    refreshed: int
    failed: int
    prerequisite_requested: int = 0
    valuation_failed: int = 0
    management_failed: int = 0
    remaining_contracts_optimized: int = 0
    reconciled_ready: int = 0
    governed_not_ready: int = 0
    governed_not_ready_opportunity_ids: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


class InstitutionalDecisionService:
    """Creates the immutable, authoritative decision record used downstream."""

    def __init__(self, session: Session, policy: InstitutionalDecisionPolicy | None = None) -> None:
        self.session = session
        self.policy = policy or InstitutionalDecisionPolicy()
        self._portfolio_snapshot_cache = None
        self._portfolio_table_available: bool | None = None

    def _ready_chain_is_complete(
        self,
        opportunity: InstitutionalOpportunityModel,
    ) -> bool:
        """Check the exact prerequisite chain behind a READY lifecycle label."""

        oid = str(opportunity.opportunity_id)
        comparison = (
            self.session.query(StrategyComparisonModel)
            .filter_by(opportunity_id=oid)
            .one_or_none()
        )
        selected_id = (
            None
            if comparison is None
            else comparison.selected_strategy_candidate_id
        )
        if not selected_id:
            return False
        strategy = self.session.get(StrategyCandidateModel, selected_id)
        if strategy is None or str(strategy.opportunity_id) != oid:
            return False
        valuation = (
            self.session.query(StrategyValuationModel)
            .filter_by(
                opportunity_id=oid,
                strategy_candidate_id=selected_id,
                selected=True,
            )
            .one_or_none()
        )
        execution = (
            self.session.query(ExecutionRecommendationModel)
            .filter_by(opportunity_id=oid)
            .one_or_none()
        )
        if valuation is None or execution is None:
            return False
        if str(execution.strategy_candidate_id) != str(selected_id):
            return False
        contract = (
            self.session.query(ContractRecommendationModel)
            .filter_by(
                contract_recommendation_id=(
                    execution.contract_recommendation_id
                ),
                opportunity_id=oid,
                strategy_candidate_id=selected_id,
                option_snapshot_id=opportunity.option_snapshot_id,
                executable=True,
            )
            .one_or_none()
        )
        if contract is None:
            return False
        management = (
            self.session.query(PositionManagementSnapshotModel)
            .filter_by(
                opportunity_id=oid,
                strategy_candidate_id=selected_id,
            )
            .first()
        )
        if management is None:
            return False
        authority = classify_trade_builder_authority(
            execution.payload_json,
            execution.ready_for_trade_builder,
        )
        return authority["authorized"] is True

    def build(self, *, opportunity_ids: Iterable[str] | None = None, limit: int | None = None) -> InstitutionalDecisionResult:
        ids = tuple(opportunity_ids or ())

        # Capture the complete decision-stage population before prerequisites
        # mutate lifecycle state. Reporting only the rows that eventually reach
        # READY_FOR_EXECUTION hides valuation and management failures.
        target_query = self.session.query(InstitutionalOpportunityModel).filter(
            InstitutionalOpportunityModel.state.in_((
                OpportunityState.CONTRACTS_OPTIMIZED.value,
                OpportunityState.READY_FOR_EXECUTION.value,
            ))
        )
        if ids:
            target_query = target_query.filter(
                InstitutionalOpportunityModel.opportunity_id.in_(ids)
            )
        target_query = target_query.order_by(
            desc(InstitutionalOpportunityModel.overall_score),
            InstitutionalOpportunityModel.symbol,
        )
        if limit is not None:
            target_query = target_query.limit(limit)
        targets = target_query.all()
        target_ids = tuple(str(item.opportunity_id) for item in targets)

        # A lifecycle label is not authority.  Partial or interrupted refreshes
        # can leave an old READY row whose current exact decision chain is no
        # longer complete.  Move only those rows back to the governed rebuild
        # point so valuation/management can repair them idempotently.
        repository = InstitutionalOpportunityRepository(self.session)
        reconciled_ready_ids: list[str] = []
        for item in targets:
            if (
                item.state == OpportunityState.READY_FOR_EXECUTION.value
                and not self._ready_chain_is_complete(item)
            ):
                repository.invalidate_ready_for_execution(
                    str(item.opportunity_id),
                    actor="m68.2.1.15-certification-reconciliation",
                    reason=(
                        "READY_FOR_EXECUTION exact strategy, contract, management, "
                        "or final certification authority is incomplete; governed "
                        "rebuild required"
                    ),
                    payload={
                        "reconciliation_version": (
                            "M68.2.1.15-CERTIFIED-DECISION-PREREQUISITES-1.0"
                        )
                    },
                )
                reconciled_ready_ids.append(str(item.opportunity_id))
        self.session.flush()

        prerequisite_ids = tuple(
            str(item[0])
            for item in (
                self.session.query(InstitutionalOpportunityModel.opportunity_id)
                .filter(
                    InstitutionalOpportunityModel.opportunity_id.in_(
                        target_ids
                    ),
                    InstitutionalOpportunityModel.state
                    == OpportunityState.CONTRACTS_OPTIMIZED.value,
                )
                .all()
                if target_ids
                else ()
            )
        )
        valuation_result = None
        management_result = None
        if prerequisite_ids:
            valuation_result = InstitutionalStrategyValuationService(self.session).value(
                opportunity_ids=prerequisite_ids, limit=None
            )
            self.session.flush()
            management_result = InstitutionalDynamicManagementService(self.session).generate(
                opportunity_ids=prerequisite_ids, limit=None
            )
            self.session.flush()

        query = self.session.query(InstitutionalOpportunityModel).filter(
            InstitutionalOpportunityModel.state == OpportunityState.READY_FOR_EXECUTION.value
        )
        if target_ids:
            query = query.filter(
                InstitutionalOpportunityModel.opportunity_id.in_(target_ids)
            )
        else:
            query = query.filter(False)
        query = query.order_by(
            desc(InstitutionalOpportunityModel.overall_score),
            InstitutionalOpportunityModel.symbol,
        )
        if limit is not None:
            query = query.limit(limit)
        opportunities = query.all()

        created = refreshed = decision_failed = 0
        errors: list[str] = []
        for opportunity in opportunities:
            opportunity_id = str(opportunity.opportunity_id)
            try:
                with self.session.begin_nested():
                    existing = self.session.query(InstitutionalDecisionSnapshotModel).filter_by(
                        opportunity_id=opportunity_id
                    ).first()
                    payload = self._assemble(opportunity)
                    state_hash = deterministic_hash(payload)
                    now = datetime.now(timezone.utc).isoformat()
                    probability = self._calibrated_probability(payload)
                    decision_snapshot_id = (
                        existing.decision_snapshot_id
                        if existing
                        else f"m62-decision-{uuid4().hex}"
                    )
                    payload_json = dict(payload)
                    payload_json.update({
                        "decision_snapshot_id": decision_snapshot_id,
                        "state_hash": state_hash,
                        "created_at": now,
                    })
                    row = InstitutionalDecisionSnapshotModel(
                        decision_snapshot_id=decision_snapshot_id,
                        opportunity_id=opportunity_id,
                        strategy_candidate_id=payload["selection"]["strategy_candidate_id"],
                        contract_recommendation_id=payload["selection"]["contract_recommendation_id"],
                        valuation_id=payload["selection"]["valuation_id"],
                        execution_recommendation_id=payload["management"]["execution_recommendation_id"],
                        management_snapshot_id=payload["management"]["management_snapshot_id"],
                        institutional_score=float(payload["scorecard"]["institutional_score"]),
                        calibrated_probability=probability,
                        expected_value=payload["valuation"].get("expected_value"),
                        capital_required=payload["valuation"].get("capital_required"),
                        selected_strategy=payload["selection"]["strategy"],
                        policy_version=self.policy.policy_version,
                        state_hash=state_hash,
                        created_at=now,
                        payload_json=payload_json,
                    )
                    self.session.merge(row)
                    self.session.flush()
                    if existing:
                        refreshed += 1
                    else:
                        created += 1
            except Exception as exc:
                decision_failed += 1
                errors.append(f"{opportunity_id}: {type(exc).__name__}: {exc}")

        remaining_rows: tuple[InstitutionalOpportunityModel, ...] = ()
        if prerequisite_ids:
            remaining_rows = tuple(
                self.session.query(InstitutionalOpportunityModel)
                    .filter(
                        InstitutionalOpportunityModel.opportunity_id.in_(prerequisite_ids),
                        InstitutionalOpportunityModel.state
                        == OpportunityState.CONTRACTS_OPTIMIZED.value,
                    )
                    .all()
            )
        prerequisite_errors: dict[str, list[str]] = {}
        for result in (valuation_result, management_result):
            for detail in (() if result is None else result.errors):
                opportunity_id = str(detail).split(":", 1)[0]
                prerequisite_errors.setdefault(opportunity_id, []).append(str(detail))
        governed_not_ready_ids: list[str] = []
        unexpected_remaining_ids: list[str] = []
        for remaining in remaining_rows:
            opportunity_id = str(remaining.opportunity_id)
            execution = (
                self.session.query(ExecutionRecommendationModel)
                .filter_by(opportunity_id=opportunity_id)
                .one_or_none()
            )
            certification = dict(
                (
                    {}
                    if execution is None
                    else (execution.payload_json or {}).get(
                        "trade_plan_certification"
                    )
                )
                or {}
            )
            disposition = str(
                certification.get("execution_disposition") or ""
            )
            if (
                certification.get("status") == "PASS"
                and disposition in {
                    "WAITING_FOR_ENTRY",
                    "REGENERATE_REQUIRED",
                }
            ):
                governed_not_ready_ids.append(opportunity_id)
                continue
            unexpected_remaining_ids.append(opportunity_id)
            errors.extend(
                prerequisite_errors.get(opportunity_id)
                or [
                    f"{opportunity_id}: prerequisite regeneration left "
                    "opportunity CONTRACTS_OPTIMIZED without a governed "
                    "non-actionable disposition"
                ]
            )

        failed = decision_failed + len(unexpected_remaining_ids)
        return InstitutionalDecisionResult(
            requested=len(target_ids),
            created=created,
            refreshed=refreshed,
            failed=failed,
            prerequisite_requested=len(prerequisite_ids),
            valuation_failed=0 if valuation_result is None else valuation_result.failed,
            management_failed=0 if management_result is None else management_result.failed,
            remaining_contracts_optimized=len(remaining_rows),
            reconciled_ready=len(reconciled_ready_ids),
            governed_not_ready=len(governed_not_ready_ids),
            governed_not_ready_opportunity_ids=tuple(
                governed_not_ready_ids
            ),
            errors=tuple(errors),
        )

    @staticmethod
    def _calibrated_probability(payload: dict) -> float | None:
        valuation = dict(payload.get("valuation") or {})
        probability = valuation.get("probability")
        if isinstance(probability, dict):
            value = probability.get("calibrated_probability")
            if value is not None:
                return float(value)
        value = valuation.get("calibrated_probability")
        return None if value is None else float(value)

    def _assemble(self, opportunity: InstitutionalOpportunityModel) -> dict:
        oid = opportunity.opportunity_id
        thesis = self.session.query(OpportunityThesisModel).filter_by(opportunity_id=oid).one()
        comparison = self.session.query(StrategyComparisonModel).filter_by(opportunity_id=oid).one()
        selected_id = comparison.selected_strategy_candidate_id
        if not selected_id:
            raise ValueError("No selected strategy")
        strategy = self.session.get(StrategyCandidateModel, selected_id)
        valuation = self.session.query(StrategyValuationModel).filter_by(
            opportunity_id=oid, strategy_candidate_id=selected_id, selected=True
        ).one()
        execution = self.session.query(ExecutionRecommendationModel).filter_by(opportunity_id=oid).one()
        if execution.strategy_candidate_id != selected_id:
            raise ValueError(
                "Execution recommendation does not match the current strategy authority"
            )
        contract = self.session.query(ContractRecommendationModel).filter_by(
            contract_recommendation_id=execution.contract_recommendation_id,
            opportunity_id=oid,
            strategy_candidate_id=selected_id,
            option_snapshot_id=opportunity.option_snapshot_id,
            executable=True,
        ).one_or_none()
        if contract is None:
            raise ValueError(
                "Execution recommendation does not reference an executable contract "
                "from the current option snapshot"
            )
        management = self.session.query(PositionManagementSnapshotModel).filter_by(
            opportunity_id=oid, strategy_candidate_id=selected_id
        ).order_by(desc(PositionManagementSnapshotModel.created_at)).first()
        if management is None:
            raise ValueError("No management snapshot")

        op_payload = dict(opportunity.payload_json or {})
        strategy_payload = dict(strategy.payload_json or {})
        valuation_payload = dict(valuation.payload_json or {})
        contract_payload = dict(contract.payload_json or {})
        execution_payload = dict(execution.payload_json or {})
        management_payload = dict(management.payload_json or {})
        underlying_quality = float(op_payload.get("metadata", {}).get("opportunity_quality", opportunity.overall_score))
        contract_quality = float(contract_payload.get("optimization_scores", {}).get("overall_contract_score", contract.liquidity_score or 0.0))
        probability_score = float(valuation.calibrated_probability or 0.0) * 100.0
        capital_efficiency = float(strategy_payload.get("metadata", {}).get("capital_efficiency_score", 0.0))
        execution_quality = float(contract_payload.get("optimization_scores", {}).get("execution_quality", 0.0))
        try:
            portfolio_context = self._portfolio_context(opportunity, valuation)
        except Exception as exc:
            # M76.2.3: preserve the decision snapshot for diagnosis, but explicitly
            # classify an implementation exception as a governance error. It is not
            # equivalent to a legitimate portfolio REJECT or to an absent snapshot.
            portfolio_context = {
                "available": False,
                "status": "ERROR",
                "routing_eligible": False,
                "portfolio_id": None,
                "portfolio_fit_score": 0.0,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "warnings": [f"PORTFOLIO_CONTEXT_ERROR:{type(exc).__name__}:{exc}"],
            }
        portfolio_fit = float(portfolio_context["portfolio_fit_score"])
        if portfolio_context["available"]:
            institutional_score = round(
                underlying_quality * 0.33 + contract_quality * 0.24 + probability_score * 0.19
                + capital_efficiency * 0.09 + execution_quality * 0.10 + portfolio_fit * 0.05,
                4,
            )
        else:
            institutional_score = round(
                underlying_quality * 0.35 + contract_quality * 0.25 + probability_score * 0.20
                + capital_efficiency * 0.10 + execution_quality * 0.10,
                4,
            )
        normalized_targets = self._normalize_targets(
            (thesis.payload_json or {}).get("targets", []),
            direction=str((thesis.payload_json or {}).get("direction", opportunity.direction)),
            entry_low=float((thesis.payload_json or {}).get("entry_zone_low", 0.0) or 0.0),
            entry_high=float((thesis.payload_json or {}).get("entry_zone_high", 0.0) or 0.0),
        )
        thesis_payload = dict(thesis.payload_json or {})
        thesis_payload["targets"] = normalized_targets
        thesis_payload["target_plan"] = [
            {"label": f"TARGET_{index}", "price": price}
            for index, price in enumerate(normalized_targets, start=1)
        ]
        management_payload["underlying_targets"] = normalized_targets
        if isinstance(management_payload.get("execution"), dict):
            management_payload["execution"]["underlying_targets"] = normalized_targets
        execution_payload["underlying_targets"] = normalized_targets
        alternatives = self.session.query(StrategyValuationModel).filter_by(opportunity_id=oid).order_by(
            desc(StrategyValuationModel.strategy_score)
        ).all()
        return {
            "policy_version": self.policy.policy_version,
            "opportunity": op_payload | {"state": opportunity.state, "version": opportunity.version},
            "thesis": thesis_payload,
            "selection": {
                "strategy_candidate_id": selected_id,
                "strategy": strategy.strategy,
                "contract_recommendation_id": contract.contract_recommendation_id,
                "valuation_id": valuation.valuation_id,
                "rationale": (comparison.payload_json or {}).get("rationale", []),
            },
            "scorecard": {
                "underlying_quality": round(underlying_quality, 4),
                "contract_quality": round(contract_quality, 4),
                "probability": round(probability_score, 4),
                "capital_efficiency": round(capital_efficiency, 4),
                "execution_quality": round(execution_quality, 4),
                "portfolio_fit": round(portfolio_fit, 4),
                "institutional_score": institutional_score,
            },
            "valuation": valuation_payload,
            "selected_contract": contract_payload,
            "strategy_alternatives": [dict(item.payload_json or {}) for item in alternatives],
            "management": management_payload | {
                "execution_recommendation_id": execution.execution_recommendation_id,
                "management_snapshot_id": management.management_snapshot_id,
                "execution": execution_payload,
            },
            "portfolio_context": portfolio_context,
            "portfolio_governance": {
                "status": str(portfolio_context.get("status") or ("AVAILABLE" if portfolio_context.get("available") else "UNAVAILABLE")),
                "routing_eligible": bool(portfolio_context.get("routing_eligible", portfolio_context.get("available", False))),
                "fail_closed": True,
                "warnings": list(portfolio_context.get("warnings") or []),
            },
            "lineage": op_payload.get("lineage", {}),
            "explainability": {
                "why_underlying": (thesis.payload_json or {}).get("evidence", []),
                "risks": (thesis.payload_json or {}).get("risks", []),
                "why_strategy": strategy_payload.get("accepted_reasons", []),
                "why_contract": contract_payload.get("validation_reasons", []),
            },
        }

    def _portfolio_context(self, opportunity: InstitutionalOpportunityModel, valuation: StrategyValuationModel) -> dict:
        if self._portfolio_table_available is None:
            self._portfolio_table_available = bool(
                PortfolioSnapshotModel is not None
                and inspect(self.session.get_bind()).has_table(PortfolioSnapshotModel.__tablename__)
            )
        if not self._portfolio_table_available:
            return {
                "available": False, "status": "UNAVAILABLE", "routing_eligible": False,
                "portfolio_id": None, "portfolio_fit_score": 0.0,
                "warnings": ["PORTFOLIO_CONTEXT_UNAVAILABLE"],
            }
        if self._portfolio_snapshot_cache is None:
            self._portfolio_snapshot_cache = self.session.query(PortfolioSnapshotModel).order_by(
                desc(PortfolioSnapshotModel.generated_at)
            ).first()
        snapshot = self._portfolio_snapshot_cache
        if snapshot is None:
            return {
                "available": False, "status": "UNAVAILABLE", "routing_eligible": False,
                "portfolio_id": None, "portfolio_fit_score": 0.0,
                "warnings": ["PORTFOLIO_CONTEXT_UNAVAILABLE"],
            }
        exposure_raw = getattr(snapshot, "exposure_json", None)
        if exposure_raw is None:
            exposure_raw = getattr(snapshot, "payload_json", None)
        exposure = dict(exposure_raw or {})
        balances = dict(exposure.get("balances") or exposure.get("capital") or {})
        # StrategyValuationModel intentionally stores the rich valuation domain
        # payload in payload_json; the physical table has no capital_required
        # column.  Read the governed domain value instead of assuming a mapped
        # attribute exists.
        valuation_payload = dict(valuation.payload_json or {})
        capital_raw = valuation_payload.get("capital_required")
        if capital_raw is None:
            capital_raw = dict(valuation_payload.get("capital") or {}).get("capital_required")
        if capital_raw is None:
            capital_raw = valuation_payload.get("maximum_loss")
        capital_required = float(capital_raw or 0.0)
        nlv = float(exposure.get("net_liquidation_value") or balances.get("net_liquidation_value") or balances.get("net_liquidation") or 0.0)
        utilization = float(exposure.get("capital_utilization_pct") or balances.get("capital_utilization_pct") or balances.get("capital_usage_pct") or 0.0)
        symbol_pct = 0.0
        by_symbol = exposure.get("by_symbol") or (exposure.get("exposures") or {}).get("by_symbol") or []
        for item in by_symbol:
            if str(item.get("key", "")).upper() == opportunity.symbol.upper():
                symbol_pct = float(item.get("capital_pct") or 0.0)
                break
        incremental_pct = (capital_required / nlv * 100.0) if nlv > 0 else 0.0
        projected_symbol_pct = symbol_pct + incremental_pct
        warnings: list[str] = []
        score = 100.0
        if utilization >= 80.0:
            score -= min(30.0, (utilization - 80.0) * 1.5)
            warnings.append("HIGH_PORTFOLIO_CAPITAL_UTILIZATION")
        if projected_symbol_pct > 10.0:
            score -= min(40.0, (projected_symbol_pct - 10.0) * 4.0)
            warnings.append("PROJECTED_SYMBOL_CONCENTRATION_ABOVE_10_PCT")
        return {
            "available": True,
            "status": "AVAILABLE",
            "routing_eligible": True,
            "portfolio_id": getattr(snapshot, "portfolio_id", None),
            "snapshot_id": getattr(snapshot, "snapshot_id", None),
            "generated_at": getattr(snapshot, "generated_at", getattr(snapshot, "snapshot_timestamp", None)),
            "capital_utilization_pct": round(utilization, 4),
            "current_symbol_exposure_pct": round(symbol_pct, 4),
            "incremental_capital_pct": round(incremental_pct, 4),
            "projected_symbol_exposure_pct": round(projected_symbol_pct, 4),
            "portfolio_fit_score": round(max(0.0, min(100.0, score)), 4),
            "warnings": warnings,
        }

    @staticmethod
    def _normalize_targets(targets, *, direction: str, entry_low: float, entry_high: float) -> list[float]:
        values = sorted({round(float(item), 6) for item in (targets or []) if item is not None})
        if direction.upper() == "BEARISH":
            return list(reversed(values))
        return values


def row_id_placeholder() -> str:
    return "PENDING"

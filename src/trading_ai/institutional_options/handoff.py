from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from trading_ai.advanced_trade_builder.contracts import LegSide, OptionRight, TradeLeg, TradePlanState
from trading_ai.advanced_trade_builder.models import TradePlanAuditModel, TradePlanModel
from trading_ai.advanced_trade_builder.service import AdvancedTradeBuilderService
from trading_ai.execution_workspace.service import ExecutionWorkspaceService

from .domain import OpportunityState
from .models import (
    ContractRecommendationModel,
    ExecutionRecommendationModel,
    InstitutionalOptionHandoffModel,
    InstitutionalOpportunityAuditModel,
    InstitutionalOpportunityModel,
    OpportunityThesisModel,
    PositionManagementSnapshotModel,
    InstitutionalDecisionSnapshotModel,
    StrategyCandidateModel,
    StrategyComparisonModel,
    StrategyValuationModel,
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class HandoffPolicy:
    minimum_capital: float = 1_000.0
    maximum_risk_budget_pct: float = 10.0
    maximum_limit_price_deviation_pct: float = 10.0
    maximum_quantity_multiplier: int = 10


@dataclass(frozen=True)
class HandoffResult:
    handoff_id: str
    opportunity_id: str
    trade_plan_id: str
    execution_intent_id: str | None
    status: str
    overrides: dict[str, Any]
    lineage: dict[str, Any]


class InstitutionalOptionsHandoffService:
    """Governed bridge from M62 recommendations to existing M56/M59 workflows."""

    def __init__(self, session: Session, policy: HandoffPolicy | None = None) -> None:
        self.session = session
        self.policy = policy or HandoffPolicy()

    def create_trade_plan(
        self,
        opportunity_id: str,
        *,
        account_id: str,
        capital: float,
        risk_budget_pct: float,
        actor: str,
        overrides: dict[str, Any] | None = None,
    ) -> HandoffResult:
        overrides = dict(overrides or {})
        bundle = self._bundle(opportunity_id)
        opp = bundle["opportunity"]
        thesis = bundle["thesis"]
        strategy = bundle["strategy"]
        contract = bundle["contract"]
        execution = bundle["execution"]
        valuation = bundle["valuation"]
        management = bundle["management"]

        if not execution.ready_for_trade_builder:
            raise ValueError("Execution recommendation is not ready for Trade Builder")
        if not contract.executable:
            raise ValueError("Selected contract recommendation is not executable")
        if float(capital) < self.policy.minimum_capital:
            raise ValueError("Capital is below the governed minimum")
        if not 0 < float(risk_budget_pct) <= self.policy.maximum_risk_budget_pct:
            raise ValueError("Risk budget percentage is outside governed limits")

        quantity_multiplier = int(overrides.get("quantity_multiplier", 1))
        if not 1 <= quantity_multiplier <= self.policy.maximum_quantity_multiplier:
            raise ValueError("quantity_multiplier is outside governed limits")

        source_legs = list(contract.payload_json.get("legs") or [])
        if not source_legs:
            raise ValueError("Exact Polygon contract legs are missing")
        limit_overrides = dict(overrides.get("limit_prices") or {})
        legs: list[TradeLeg] = []
        normalized_legs: list[dict[str, Any]] = []
        for raw in source_legs:
            symbol = str(raw.get("option_symbol") or "").strip()
            if not symbol:
                raise ValueError("Every handoff leg requires an exact Polygon option_symbol")
            side = str(raw.get("side") or "").upper()
            default_price = float(raw.get("ask") or raw.get("last") or 0) if side == "BUY" else float(raw.get("bid") or raw.get("last") or 0)
            selected_price = float(limit_overrides.get(symbol, default_price))
            if default_price <= 0 or selected_price <= 0:
                raise ValueError(f"Executable limit price is missing for {symbol}")
            deviation = abs(selected_price - default_price) / default_price * 100.0
            if deviation > self.policy.maximum_limit_price_deviation_pct:
                raise ValueError(f"Limit-price override for {symbol} exceeds governed deviation")
            option_type = str(raw.get("option_type") or "").upper()
            leg = TradeLeg(
                side=LegSide(side),
                quantity=max(1, int(raw.get("quantity_ratio") or 1)) * quantity_multiplier,
                option_right=OptionRight("CALL" if option_type in {"CALL", "C"} else "PUT"),
                strike=float(raw["strike"]),
                expiry=str(raw["expiry"]),
                limit_price=selected_price,
                delta=raw.get("delta"), gamma=raw.get("gamma"), theta=raw.get("theta"), vega=raw.get("vega"),
                option_symbol=symbol,
            )
            legs.append(leg)
            normalized_legs.append({
                "side": leg.side.value, "quantity": leg.quantity, "option_right": leg.option_right.value,
                "strike": leg.strike, "expiry": leg.expiry, "limit_price": leg.limit_price,
                "delta": leg.delta, "gamma": leg.gamma, "theta": leg.theta, "vega": leg.vega,
                "option_symbol": leg.option_symbol,
            })

        debit, credit, max_loss, max_profit, rr, budget, greeks, checks = AdvancedTradeBuilderService.economics(tuple(legs), float(capital), float(risk_budget_pct))
        checks.update({
            "m62_selected_strategy": bool(strategy.selected),
            "m62_exact_polygon_contracts": len({x["option_symbol"] for x in normalized_legs}) == len(normalized_legs),
            "m62_thesis_lineage": bool(opp.stock_state_hash and opp.stock_scanner_run_id),
            "m62_dynamic_management": bool(execution.payload_json.get("underlying_targets") and execution.underlying_stop),
            "m62_override_governance": True,
        })
        checks["valid"] = all(bool(value) for value in checks.values())
        state = TradePlanState.VALIDATED.value if checks["valid"] else TradePlanState.DRAFT.value

        lineage = {
            "source": "M62_INSTITUTIONAL_OPTIONS",
            "institutional_opportunity_id": opp.opportunity_id,
            "institutional_opportunity_version": opp.version,
            "stock_publication_name": opp.stock_publication_name,
            "stock_scanner_run_id": opp.stock_scanner_run_id,
            "stock_candidate_id": opp.stock_candidate_id,
            "stock_state_hash": opp.stock_state_hash,
            "option_snapshot_id": contract.option_snapshot_id,
            "strategy_candidate_id": strategy.strategy_candidate_id,
            "contract_recommendation_id": contract.contract_recommendation_id,
            "execution_recommendation_id": execution.execution_recommendation_id,
            "valuation_id": valuation.valuation_id if valuation else None,
            "management_snapshot_id": management.management_snapshot_id if management else None,
        }
        execution_payload = dict(execution.payload_json or {})
        management_payload = dict(management.payload_json or {}) if management else {}
        dynamic_management = {
            "underlying_entry_zone_low": thesis.entry_zone_low,
            "underlying_entry_zone_high": thesis.entry_zone_high,
            "underlying_stop": execution.underlying_stop,
            "underlying_targets": list(execution_payload.get("underlying_targets") or []),
            "target_labels": list(execution_payload.get("target_labels") or []),
            "trailing_policy": execution.trailing_policy,
            "emergency_option_stop_pct": execution_payload.get("emergency_option_stop_pct"),
            "theta_exit_days_to_expiry": execution_payload.get("theta_exit_days_to_expiry"),
            "volatility_exit_rule": execution_payload.get("volatility_exit_rule"),
            "assignment_risk_rule": management_payload.get("assignment_risk_rule"),
            "liquidity_exit_rule": management_payload.get("liquidity_exit_rule"),
            "partial_profit_fraction": management_payload.get("partial_profit_fraction"),
            "invalidation_reasons": list(execution_payload.get("invalidation_reasons") or []),
            "thesis_integrity": management.thesis_integrity if management else None,
            "position_health": management.position_health if management else None,
            "management_action": management.action if management else None,
            "management_mode": "PLATFORM_MANAGED_AFTER_FILL",
            "broker_protection_status": "NOT_SUBMITTED",
        }
        thesis_payload = dict(thesis.payload_json)
        governed_overrides = {
            "quantity_multiplier": quantity_multiplier,
            "limit_prices": limit_overrides,
            "account_id": account_id,
            "capital": float(capital),
            "risk_budget_pct": float(risk_budget_pct),
        }

        existing = self.session.scalar(select(InstitutionalOptionHandoffModel).where(
            InstitutionalOptionHandoffModel.opportunity_id == opportunity_id,
            InstitutionalOptionHandoffModel.account_id == account_id,
            InstitutionalOptionHandoffModel.strategy_candidate_id == strategy.strategy_candidate_id,
        ).order_by(desc(InstitutionalOptionHandoffModel.created_at)))
        if existing and existing.trade_plan_id:
            existing_plan = self.session.get(TradePlanModel, existing.trade_plan_id)
            if existing_plan is not None:
                previous_state = existing_plan.state
                if existing_plan.state == TradePlanState.DRAFT.value:
                    existing_plan.opportunity_version = opp.version
                    existing_plan.intelligence_id = opp.stock_state_hash
                    existing_plan.account_id = account_id
                    existing_plan.symbol = opp.symbol
                    existing_plan.direction = opp.direction
                    existing_plan.strategy = strategy.strategy
                    existing_plan.version += 1
                    existing_plan.capital = float(capital)
                    existing_plan.risk_budget_pct = float(risk_budget_pct)
                    existing_plan.risk_budget_amount = budget
                    existing_plan.estimated_debit = debit
                    existing_plan.estimated_credit = credit
                    existing_plan.max_loss = max_loss
                    existing_plan.max_profit = max_profit
                    existing_plan.reward_risk_ratio = rr
                    existing_plan.net_greeks_json = greeks
                    existing_plan.validation_json = checks
                    existing_plan.legs_json = normalized_legs
                    existing_plan.state = state
                    self.session.add(TradePlanAuditModel(
                        audit_id=f"TPA-M62-{uuid4().hex.upper()}", trade_plan_id=existing_plan.trade_plan_id,
                        trade_plan_version=existing_plan.version, event_type="M62_TRADE_PLAN_REVALIDATED", actor=actor,
                        reason="Governed DRAFT revalidation using current M62 recommendation and Trade Builder risk configuration",
                        event_timestamp=now(), payload_json={"previous_state": previous_state, "new_state": state, "validation": checks, "lineage": lineage, "risk": governed_overrides},
                    ))
                existing_plan.execution_intent_json = {
                    **dict(existing_plan.execution_intent_json or {}),
                    "m62_lineage": lineage,
                    "underlying_thesis": thesis_payload,
                    "dynamic_management": dynamic_management,
                    "decision_snapshot_id": bundle["decision"].decision_snapshot_id,
                    "decision_state_hash": bundle["decision"].state_hash,
                }
                existing_plan.updated_at = now()
            existing.contract_recommendation_id = contract.contract_recommendation_id
            existing.execution_recommendation_id = execution.execution_recommendation_id
            existing.overrides_json = governed_overrides
            existing.lineage_json = lineage
            existing.payload_json = {
                **dict(existing.payload_json or {}),
                "thesis": thesis_payload,
                "dynamic_management": dynamic_management,
                "validation": checks,
            }
            existing.status = "TRADE_PLAN_VALIDATED" if state == TradePlanState.VALIDATED.value else "TRADE_PLAN_REVALIDATED_DRAFT"
            existing.updated_at = now()
            self.session.commit()
            return HandoffResult(existing.handoff_id, opportunity_id, existing.trade_plan_id, existing.execution_intent_id, existing.status, dict(existing.overrides_json), dict(existing.lineage_json))

        ts = now()
        plan = TradePlanModel(
            trade_plan_id=f"TP-M62-{uuid4().hex.upper()}", opportunity_id=opp.opportunity_id,
            opportunity_version=opp.version, intelligence_id=opp.stock_state_hash, account_id=account_id,
            symbol=opp.symbol, direction=opp.direction, strategy=strategy.strategy, state=state, version=1,
            capital=float(capital), risk_budget_pct=float(risk_budget_pct), risk_budget_amount=budget,
            estimated_debit=debit, estimated_credit=credit, max_loss=max_loss,
            max_profit=max_profit, reward_risk_ratio=rr, net_greeks_json=greeks,
            validation_json=checks, legs_json=normalized_legs,
            execution_intent_json={"m62_lineage": lineage, "underlying_thesis": thesis_payload, "dynamic_management": dynamic_management, "decision_snapshot_id": bundle["decision"].decision_snapshot_id, "decision_state_hash": bundle["decision"].state_hash},
            notes="Generated from Milestone 62 Institutional Options recommendation",
            created_by=actor, created_at=ts, updated_at=ts,
        )
        self.session.add(plan)
        self.session.add(TradePlanAuditModel(
            audit_id=f"TPA-M62-{uuid4().hex.upper()}", trade_plan_id=plan.trade_plan_id,
            trade_plan_version=1, event_type="M62_TRADE_PLAN_HANDOFF", actor=actor,
            reason="Created from selected Institutional Options strategy and exact Polygon contracts",
            event_timestamp=ts, payload_json={"lineage": lineage, "overrides": governed_overrides, "dynamic_management": dynamic_management, "decision_snapshot_id": bundle["decision"].decision_snapshot_id, "decision_state_hash": bundle["decision"].state_hash},
        ))
        handoff = InstitutionalOptionHandoffModel(
            handoff_id=f"m62-handoff-{uuid4().hex}", opportunity_id=opportunity_id,
            strategy_candidate_id=strategy.strategy_candidate_id,
            contract_recommendation_id=contract.contract_recommendation_id,
            execution_recommendation_id=execution.execution_recommendation_id,
            account_id=account_id, trade_plan_id=plan.trade_plan_id, execution_intent_id=None,
            status="TRADE_PLAN_CREATED", overrides_json=governed_overrides, lineage_json=lineage,
            payload_json={"thesis": thesis_payload, "dynamic_management": dynamic_management, "validation": checks},
            created_at=ts, updated_at=ts,
        )
        self.session.add(handoff)
        self._opportunity_audit(opp, actor, "M62_TRADE_BUILDER_HANDOFF", {"trade_plan_id": plan.trade_plan_id, "handoff_id": handoff.handoff_id})
        self.session.commit()
        return HandoffResult(handoff.handoff_id, opportunity_id, plan.trade_plan_id, None, handoff.status, governed_overrides, lineage)

    def revalidate_trade_plan(self, trade_plan_id: str, *, actor: str) -> HandoffResult:
        from .trade_builder_config import load_trade_builder_risk_config

        plan = self.session.get(TradePlanModel, trade_plan_id)
        if plan is None:
            raise LookupError("Trade plan not found")
        if plan.state != TradePlanState.DRAFT.value:
            raise ValueError("Only DRAFT trade plans can be revalidated")
        handoff = self.session.scalar(select(InstitutionalOptionHandoffModel).where(
            InstitutionalOptionHandoffModel.trade_plan_id == trade_plan_id
        ).order_by(desc(InstitutionalOptionHandoffModel.created_at)))
        if handoff is None:
            raise LookupError("Institutional Options handoff not found for trade plan")
        bundle = self._bundle(handoff.opportunity_id)
        current_strategy = bundle["strategy"]
        if handoff.strategy_candidate_id != current_strategy.strategy_candidate_id:
            raise ValueError("Selected Institutional Options strategy changed; create a new trade plan instead of revalidating the stale strategy")
        config = load_trade_builder_risk_config()
        return self.create_trade_plan(
            handoff.opportunity_id,
            account_id=plan.account_id,
            capital=config.capital,
            risk_budget_pct=config.risk_budget_pct,
            actor=actor,
            overrides=dict(handoff.overrides_json or {}),
        )

    def create_execution_intent(self, handoff_id: str, *, actor: str, portfolio_id: str | None = None) -> HandoffResult:
        handoff = self.session.get(InstitutionalOptionHandoffModel, handoff_id)
        if handoff is None:
            raise LookupError("Institutional Options handoff not found")
        plan = self.session.get(TradePlanModel, handoff.trade_plan_id)
        if plan is None:
            raise LookupError("Trade plan not found")
        if plan.state != TradePlanState.PAPER_READY.value:
            raise ValueError("Trade plan must be PAPER_READY before creating an execution intent")
        intent = ExecutionWorkspaceService(self.session).create_from_trade_plan(plan.trade_plan_id, actor, portfolio_id)
        handoff.execution_intent_id = intent["execution_intent_id"]
        handoff.status = "EXECUTION_INTENT_CREATED"
        handoff.updated_at = now()
        self.session.commit()
        return HandoffResult(handoff.handoff_id, handoff.opportunity_id, handoff.trade_plan_id, handoff.execution_intent_id, handoff.status, dict(handoff.overrides_json), dict(handoff.lineage_json))

    def _bundle(self, opportunity_id: str) -> dict[str, Any]:
        decision = self.session.scalar(select(InstitutionalDecisionSnapshotModel).where(InstitutionalDecisionSnapshotModel.opportunity_id == opportunity_id))
        opp = self.session.get(InstitutionalOpportunityModel, opportunity_id)
        if opp is None:
            raise LookupError("Institutional Opportunity not found")
        if opp.state not in {OpportunityState.CONTRACTS_OPTIMIZED.value, OpportunityState.READY_FOR_EXECUTION.value}:
            raise ValueError("Opportunity must have optimized contracts before handoff")
        thesis = self.session.scalar(select(OpportunityThesisModel).where(OpportunityThesisModel.opportunity_id == opportunity_id))
        comparison = self.session.scalar(select(StrategyComparisonModel).where(StrategyComparisonModel.opportunity_id == opportunity_id))
        selected_id = comparison.selected_strategy_candidate_id if comparison else None
        strategy = self.session.get(StrategyCandidateModel, selected_id) if selected_id else None
        if strategy is None:
            strategy = self.session.scalar(select(StrategyCandidateModel).where(StrategyCandidateModel.opportunity_id == opportunity_id, StrategyCandidateModel.selected.is_(True)))
        if strategy is None:
            raise ValueError("No selected strategy is available for handoff")
        contract = self.session.scalar(select(ContractRecommendationModel).where(
            ContractRecommendationModel.opportunity_id == opportunity_id,
            ContractRecommendationModel.strategy_candidate_id == strategy.strategy_candidate_id,
            ContractRecommendationModel.executable.is_(True),
        ).order_by(desc(ContractRecommendationModel.created_at)))
        execution = self.session.scalar(select(ExecutionRecommendationModel).where(ExecutionRecommendationModel.opportunity_id == opportunity_id))
        valuation = self.session.scalar(select(StrategyValuationModel).where(StrategyValuationModel.opportunity_id == opportunity_id, StrategyValuationModel.strategy_candidate_id == strategy.strategy_candidate_id))
        management = self.session.scalar(select(PositionManagementSnapshotModel).where(PositionManagementSnapshotModel.opportunity_id == opportunity_id, PositionManagementSnapshotModel.strategy_candidate_id == strategy.strategy_candidate_id).order_by(desc(PositionManagementSnapshotModel.created_at)))
        if thesis is None or contract is None or execution is None:
            raise ValueError("Opportunity handoff bundle is incomplete")
        if decision is None:
            # Backward-compatible snapshot materialization for pre-m62_005 records.
            from .domain import deterministic_hash
            payload = {
                "policy_version": "M62-HANDOFF-MATERIALIZED-1.0",
                "opportunity": dict(opp.payload_json or {}),
                "thesis": dict(thesis.payload_json or {}),
                "selection": {
                    "strategy_candidate_id": strategy.strategy_candidate_id,
                    "strategy": strategy.strategy,
                    "contract_recommendation_id": contract.contract_recommendation_id,
                    "valuation_id": None if valuation is None else valuation.valuation_id,
                },
                "selected_contract": dict(contract.payload_json or {}),
                "valuation": {} if valuation is None else dict(valuation.payload_json or {}),
                "management": {} if management is None else dict(management.payload_json or {}),
                "lineage": dict((opp.payload_json or {}).get("lineage") or {}),
            }
            state_hash = deterministic_hash(payload)
            decision = InstitutionalDecisionSnapshotModel(
                decision_snapshot_id=f"m62-decision-{uuid4().hex}",
                opportunity_id=opportunity_id,
                strategy_candidate_id=strategy.strategy_candidate_id,
                contract_recommendation_id=contract.contract_recommendation_id,
                valuation_id="LEGACY" if valuation is None else valuation.valuation_id,
                execution_recommendation_id=execution.execution_recommendation_id,
                management_snapshot_id="LEGACY" if management is None else management.management_snapshot_id,
                institutional_score=float(strategy.strategy_score or strategy.eligibility_score or 0.0),
                calibrated_probability=None if valuation is None else valuation.calibrated_probability,
                expected_value=None if valuation is None else valuation.expected_value,
                capital_required=(dict(strategy.payload_json or {}).get("capital_required")),
                selected_strategy=strategy.strategy,
                policy_version="M62-HANDOFF-MATERIALIZED-1.0",
                state_hash=state_hash,
                created_at=now(),
                payload_json=payload | {"state_hash": state_hash},
            )
            self.session.add(decision)
            self.session.flush()
        return {"opportunity": opp, "thesis": thesis, "strategy": strategy, "contract": contract, "execution": execution, "valuation": valuation, "management": management, "decision": decision}

    def _opportunity_audit(self, opp: InstitutionalOpportunityModel, actor: str, reason: str, payload: dict[str, Any]) -> None:
        self.session.add(InstitutionalOpportunityAuditModel(
            audit_id=f"m62-audit-{uuid4().hex}", opportunity_id=opp.opportunity_id,
            previous_state=opp.state, new_state=opp.state, actor=actor, reason=reason,
            event_timestamp=now(), payload_json=payload,
        ))

from __future__ import annotations

from datetime import date, datetime, timezone
from math import ceil
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trading_ai.advanced_trade_builder.models import TradePlanModel
from trading_ai.authoritative_paper_trading.database_models import CanonicalOrderModel
from trading_ai.broker.ibkr.database_models import BrokerAccountBindingModel
from trading_ai.broker.ibkr.models import IbkrPaperConnectionConfig
from trading_ai.broker.ibkr.order_models import IbkrPaperComboLegRequest, IbkrPaperComboOrderRequest, IbkrPaperOrderRequest
from trading_ai.broker.ibkr.order_service import IbkrPaperOrderService
from trading_ai.broker.ibkr.order_transport import IbapiPaperOrderTransport
from trading_ai.execution_workspace.models import ExecutionIntentModel
from trading_ai.portfolio_intelligence.models import ManagedPositionModel, PositionEventModel, PositionHealthSnapshotModel
from trading_ai.position_management.database_models import PositionExitInstructionModel, PositionMonitoringAssessmentModel

from .contracts import AutomationMode, ManagementCycleResult, ManagementEvaluation


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class DynamicPositionManagementService:
    """Milestone 62 Phase 10 fill-to-exit control loop.

    The service intentionally operates on persisted broker/execution/market data.  It
    does not pretend that a dynamic structural or volatility rule is a static IBKR
    stop order.  It evaluates those rules and creates governed closing instructions;
    FULLY_AUTOMATIC mode may submit paper closing orders after all safety gates pass.
    """

    ACTIVE_STATES = {"OPEN", "PARTIAL", "HEDGED", "ROLLED"}
    M74_14_VERSION = "M74.14-UNIFIED-EXIT-MATERIALIZATION-AUTONOMOUS-HEALTH-1.0"
    LEGACY_CANONICAL_MISSING_FRAGMENT = "canonical order not found: M62-EXIT-"
    CRITICAL_PROTECTION_LABELS = {"EMERGENCY_OPTION_STOP", "EXPIRATION_GUARD_EXIT", "STRUCTURAL_STOP", "SHORT_LEG_ASSIGNMENT_EXIT", "THETA_EXIT", "VOLATILITY_EXIT"}
    PROFIT_TARGET_LABELS = {"TARGET_1", "TARGET_2", "TARGET_3"}

    def __init__(self, session: Session):
        self.s = session

    def set_mode(self, position_id: str, mode: str, actor: str, reason: str) -> dict:
        row = self.s.get(ManagedPositionModel, position_id)
        if not row:
            raise KeyError("Managed position not found")
        resolved = AutomationMode(mode)
        metadata = dict(row.metadata_json or {})
        previous = metadata.get("automation_mode", AutomationMode.ADVISORY.value)
        metadata["automation_mode"] = resolved.value
        metadata["automation_mode_reason"] = reason
        metadata["automation_mode_updated_by"] = actor
        metadata["automation_mode_updated_at"] = utc_now()
        row.version += 1
        row.metadata_json = metadata
        row.updated_at = utc_now()
        self._event(row, "AUTOMATION_MODE_CHANGED", actor, reason, {"previous": previous, "new": resolved.value})
        self.s.commit()
        return self._position_payload(row)

    def evaluate_all(self, portfolio_id: str | None = None, position_ids: list[str] | None = None,
                     actor: str = "m62-phase10", submit_automatic: bool = True,
                     limit: int = 250) -> ManagementCycleResult:
        query = select(ManagedPositionModel).where(ManagedPositionModel.state.in_(self.ACTIVE_STATES)).order_by(ManagedPositionModel.updated_at).limit(limit)
        if portfolio_id:
            query = query.where(ManagedPositionModel.portfolio_id == portfolio_id)
        if position_ids:
            query = query.where(ManagedPositionModel.position_id.in_(position_ids))
        rows = list(self.s.scalars(query))
        evaluations: list[ManagementEvaluation] = []
        errors: list[str] = []
        counts = {"triggered": 0, "advisory": 0, "pending": 0, "submitted": 0, "failed": 0}
        for row in rows:
            position_id = row.position_id
            try:
                with self.s.begin_nested():
                    result = self.evaluate_position(position_id, actor=actor, submit_automatic=submit_automatic)
                    evaluations.append(result)
                    counts["triggered"] += len(result.triggered_instructions)
                    for item in result.triggered_instructions:
                        status = item.get("status")
                        if status == "TRIGGERED_ADVISORY": counts["advisory"] += 1
                        elif status == "PENDING_APPROVAL": counts["pending"] += 1
                        elif status in {"SUBMITTED", "ACKNOWLEDGED"}: counts["submitted"] += 1
                self.s.commit()
            except Exception as exc:
                self.s.rollback()
                counts["failed"] += 1
                errors.append(f"{position_id}: {type(exc).__name__}: {exc}")
        return ManagementCycleResult(len(rows), len(evaluations), counts["triggered"], counts["advisory"], counts["pending"], counts["submitted"], counts["failed"], tuple(errors), tuple(evaluations))

    def evaluate_position(self, position_id: str, actor: str = "m62-phase10", submit_automatic: bool = True) -> ManagementEvaluation:
        position = self.s.get(ManagedPositionModel, position_id)
        if not position:
            raise KeyError("Managed position not found")
        if position.state not in self.ACTIVE_STATES:
            raise ValueError(f"Position state {position.state} is not dynamically manageable")
        metadata = dict(position.metadata_json or {})
        management = dict(metadata.get("dynamic_management") or {})
        mode = AutomationMode(metadata.get("automation_mode", AutomationMode.ADVISORY.value))
        market = self._market_snapshot(position, management)
        current_stop, trailing_updated = self._advance_trailing_stop(position, management, market, actor)
        instructions = self._instructions(position.position_id)
        repaired_failures = self._rearm_legacy_canonical_missing_failures(position, instructions, actor)
        if repaired_failures:
            metadata["m74_14_exit_recovery"] = {
                "version": self.M74_14_VERSION,
                "rearmed_count": repaired_failures,
                "rearmed_at": utc_now(),
                "reason": "LEGACY_CANONICAL_EXIT_ORDER_MISSING",
            }
        triggered: list[dict] = []
        priority={"EMERGENCY_OPTION_STOP":0,"EXPIRATION_GUARD_EXIT":1,"STRUCTURAL_STOP":2,"SHORT_LEG_ASSIGNMENT_EXIT":3,"THETA_EXIT":4,"VOLATILITY_EXIT":5,"TARGET_3":6,"TARGET_2":7,"TARGET_1":8}
        eligible=[]
        for instruction in instructions:
            payload=dict(instruction.payload or {})
            if instruction.status not in {"ARMED","SUBMISSION_FAILED"}:continue
            if self._triggered(position,payload,market,current_stop):eligible.append((priority.get(str(payload.get("label")),99),instruction))
        for _,instruction in sorted(eligible,key=lambda x:x[0])[:1]:
            payload = dict(instruction.payload or {})
            status = self._govern_instruction(position, instruction, mode, actor)
            item = {"instruction_id": instruction.instruction_id, "label": payload.get("label"), "action": instruction.action,
                    "quantity": instruction.quantity, "status": status, "trigger_type": payload.get("trigger_type"),
                    "trigger_value": payload.get("trigger_value")}
            if mode is AutomationMode.FULLY_AUTOMATIC and submit_automatic and status == "READY_FOR_AUTOMATIC_SUBMISSION":
                try:
                    broker = self._submit_exit(position, instruction, actor)
                    instruction.status = "SUBMITTED"
                    payload.pop("submission_error", None)
                    payload.pop("submission_failed_at", None)
                    payload["broker_submission"] = broker
                    payload["submitted_at"] = utc_now()
                    payload["submission_recovered"] = bool(dict(broker or {}).get("canonical_exit_order", {}).get("source") in {"M74_13_1_SELF_HEALING_MATERIALIZATION", "CONCURRENT_CANONICAL_EXIT_ORDER"})
                    instruction.payload = payload
                    item["status"] = "SUBMITTED"
                except Exception as exc:
                    instruction.status = "SUBMISSION_FAILED"
                    payload["submission_attempt_count"] = int(payload.get("submission_attempt_count") or 0) + 1
                    payload["submission_error"] = f"{type(exc).__name__}: {exc}"
                    payload["submission_failed_at"] = utc_now()
                    instruction.payload = payload
                    item["status"] = "SUBMISSION_FAILED"
            triggered.append(item)
        health = self._health(position, market, current_stop)
        position.version += 1
        position.mark_json = {**dict(position.mark_json or {}), **market["mark"]}
        position.health_json = health
        position.decision_json = self._decision(triggered, health)
        metadata["dynamic_management"] = {**management, "current_underlying_stop": current_stop}
        metadata["automation_mode"] = mode.value
        metadata["last_management_evaluation_at"] = utc_now()
        metadata["last_management_status"] = "ACTION_TRIGGERED" if triggered else "HOLD"
        position.metadata_json = metadata
        position.updated_at = utc_now()
        self.s.add(PositionHealthSnapshotModel(health_snapshot_id=f"PHS-{uuid4().hex.upper()}", position_id=position.position_id,
            position_version=position.version, snapshot_timestamp=position.updated_at, health_score=health["score"],
            direction=health["direction"], confidence=health["confidence"], payload_json=health))
        self._event(position, "DYNAMIC_MANAGEMENT_EVALUATED", actor,
                    "Dynamic management cycle evaluated", {"market": market, "triggered": triggered, "mode": mode.value})
        self.s.flush()
        targets = [float(x) for x in (management.get("underlying_targets") or []) if _float(x) is not None]
        next_target = self._next_target(position.direction, targets, market.get("underlying_price"))
        return ManagementEvaluation(position.position_id, position.symbol, mode.value, market.get("underlying_price"),
            market.get("option_mark"), market.get("days_to_expiry"), current_stop, next_target, tuple(triggered),
            trailing_updated, health["thesis_integrity"], "ACTION_TRIGGERED" if triggered else "HOLD", position.updated_at)

    def _is_legacy_canonical_missing_failure(self, instruction) -> bool:
        if str(instruction.status or '').upper() != "SUBMISSION_FAILED":
            return False
        payload = dict(instruction.payload or {})
        return self.LEGACY_CANONICAL_MISSING_FRAGMENT in str(payload.get("submission_error") or "")

    def _rearm_legacy_canonical_missing_failures(self, position, instructions, actor: str) -> int:
        """Repair the pre-M74.13.1 failure mode without erasing audit evidence.

        The old manager could mark an otherwise-valid instruction SUBMISSION_FAILED before
        the deterministic M62-EXIT canonical order existed.  M74.13.1 fixed the routing
        path, but those persisted statuses remained terminal-looking and therefore never
        re-entered the unified submission path unless explicitly repaired.  M74.14 turns
        only that known construction failure back into ARMED.  The original error is
        retained in submission_failure_history; no broker order is transmitted here.
        """
        repaired = 0
        now = utc_now()
        for instruction in instructions:
            if not self._is_legacy_canonical_missing_failure(instruction):
                continue
            payload = dict(instruction.payload or {})
            history = list(payload.get("submission_failure_history") or [])
            history.append({
                "error": payload.get("submission_error"),
                "failed_at": payload.get("submission_failed_at"),
                "superseded_at": now,
                "superseded_by": self.M74_14_VERSION,
                "recovery": "REARM_FOR_UNIFIED_EXIT_MATERIALIZATION",
            })
            payload["submission_failure_history"] = history[-20:]
            payload["legacy_submission_error_superseded"] = payload.get("submission_error")
            payload["legacy_submission_failed_at_superseded"] = payload.get("submission_failed_at")
            payload.pop("submission_error", None)
            payload.pop("submission_failed_at", None)
            payload["submission_recovery_state"] = "REARMED_FOR_UNIFIED_EXIT_MATERIALIZATION"
            payload["submission_recovered_at"] = now
            payload["submission_recovered_by"] = actor
            payload["unified_exit_materialization_version"] = self.M74_14_VERSION
            instruction.payload = payload
            instruction.status = "ARMED"
            repaired += 1
        if repaired:
            self._event(position, "LEGACY_EXIT_SUBMISSION_FAILURES_REARMED", actor,
                        "Re-armed legacy canonical-order-missing exits for unified materialization",
                        {"count": repaired, "version": self.M74_14_VERSION})
        return repaired

    def repair_legacy_submission_failures(self, portfolio_id: str | None = None, actor: str = "M74_14_REPAIR") -> dict:
        """Idempotently re-arm only legacy canonical-order-missing exit failures.

        This is safe to run as an operational repair: it does not submit an order and it
        does not alter failures caused by IBKR, price governance, contract resolution, or
        any other downstream condition.  The next normal management cycle decides whether
        each re-armed instruction is currently triggered and, if so, routes it through the
        unified self-healing materializer.
        """
        query = select(ManagedPositionModel).where(ManagedPositionModel.state.in_(self.ACTIVE_STATES))
        if portfolio_id:
            query = query.where(ManagedPositionModel.portfolio_id == portfolio_id)
        positions = list(self.s.scalars(query))
        repaired_positions = 0
        repaired_instructions = 0
        details = []
        for position in positions:
            instructions = self._instructions(position.position_id)
            repaired = self._rearm_legacy_canonical_missing_failures(position, instructions, actor)
            if not repaired:
                continue
            repaired_positions += 1
            repaired_instructions += repaired
            metadata = dict(position.metadata_json or {})
            metadata["m74_14_exit_recovery"] = {
                "version": self.M74_14_VERSION,
                "rearmed_count": repaired,
                "rearmed_at": utc_now(),
                "reason": "LEGACY_CANONICAL_EXIT_ORDER_MISSING",
            }
            position.metadata_json = metadata
            position.updated_at = utc_now()
            details.append({"position_id": position.position_id, "symbol": position.symbol, "rearmed": repaired})
        self.s.commit()
        return {
            "version": self.M74_14_VERSION,
            "portfolio_id": portfolio_id,
            "positions_scanned": len(positions),
            "positions_repaired": repaired_positions,
            "instructions_rearmed": repaired_instructions,
            "details": details,
        }

    def approve_instruction(self, instruction_id: str, actor: str, reason: str, submit: bool = False) -> dict:
        instruction = self.s.scalar(select(PositionExitInstructionModel).where(PositionExitInstructionModel.instruction_id == instruction_id))
        if not instruction:
            raise KeyError("Exit instruction not found")
        position = self.s.get(ManagedPositionModel, instruction.position_id)
        if not position:
            raise KeyError("Managed position not found")
        if instruction.status not in {"PENDING_APPROVAL", "TRIGGERED_ADVISORY", "SUBMISSION_FAILED"}:
            raise ValueError(f"Instruction status {instruction.status} cannot be approved")
        instruction.status = "APPROVED"
        payload = dict(instruction.payload or {})
        payload["approved_by"] = actor; payload["approved_at"] = utc_now(); payload["approval_reason"] = reason
        instruction.payload = payload
        if submit:
            broker = self._submit_exit(position, instruction, actor)
            instruction.status = "SUBMITTED"
            payload["broker_submission"] = broker; payload["submitted_at"] = utc_now(); instruction.payload = payload
        self._event(position, "EXIT_INSTRUCTION_APPROVED", actor, reason, {"instruction_id": instruction_id, "submitted": submit})
        self.s.commit()
        return self._instruction_payload(instruction)

    def list_instructions(self, position_id: str | None = None, status: str | None = None) -> list[dict]:
        query = select(PositionExitInstructionModel).order_by(PositionExitInstructionModel.created_at.desc())
        if position_id: query = query.where(PositionExitInstructionModel.position_id == position_id)
        if status: query = query.where(PositionExitInstructionModel.status == status)
        return [self._instruction_payload(x) for x in self.s.scalars(query)]

    def _market_snapshot(self, position: ManagedPositionModel, management: dict) -> dict:
        # M73 injects a direct Polygon snapshot immediately before every autonomous
        # management evaluation. Persisted history remains the fallback for advisory
        # / offline workflows only.
        live = dict((position.metadata_json or {}).get("m73_live_market") or {})
        if live.get("source") == "POLYGON_DIRECT" and live.get("underlying_price") is not None:
            return live
        underlying = self.s.execute(text("SELECT close, high, low, date::text FROM price_history WHERE UPPER(symbol)=UPPER(:symbol) ORDER BY date DESC LIMIT 2"), {"symbol": position.symbol}).mappings().all()
        current = underlying[0] if underlying else {}
        previous = underlying[1] if len(underlying) > 1 else {}
        trade_plan = self.s.get(TradePlanModel, position.trade_plan_id)
        legs = list(trade_plan.legs_json or []) if trade_plan else []
        option_rows=[]
        for leg in legs:
            symbol = str(leg.get("option_symbol") or "")
            if not symbol: continue
            row = self.s.execute(text("SELECT bid,ask,last,mid,delta,gamma,theta,vega,implied_volatility,expiry::text,quote_date::text FROM option_contract_history WHERE option_symbol=:symbol ORDER BY quote_date DESC,id DESC LIMIT 1"), {"symbol": symbol}).mappings().first()
            if row: option_rows.append((leg,row))
        net_mark=0.0; delta=gamma=theta=vega=0.0; expiries=[]; ivs=[]
        for leg,row in option_rows:
            mid=_float(row.get("mid"),0) or ((_float(row.get("bid"),0)+_float(row.get("ask"),0))/2)
            sign=1 if str(leg.get("side","BUY")).upper()=="BUY" else -1
            ratio=max(1,int(float(leg.get("quantity",1))))
            net_mark += sign*ratio*mid; delta += sign*ratio*(_float(row.get("delta"),0) or 0); gamma += sign*ratio*(_float(row.get("gamma"),0) or 0); theta += sign*ratio*(_float(row.get("theta"),0) or 0); vega += sign*ratio*(_float(row.get("vega"),0) or 0)
            ivs.append(_float(row.get("implied_volatility"),0) or 0)
            try: expiries.append(date.fromisoformat(str(row.get("expiry"))))
            except Exception: pass
        qty=_float(position.mark_json.get("quantity"),1) or 1
        entry=max(_float(position.entry_value,0) or 0,0.01)
        market_value=abs(net_mark)*qty*100 if option_rows else _float(position.mark_json.get("market_value"),0) or 0
        upnl=market_value-entry
        ret=upnl/entry*100
        dte=min([(x-date.today()).days for x in expiries],default=position.mark_json.get("days_to_expiry"))
        initial_iv=_float(position.metadata_json.get("entry_implied_volatility"))
        current_iv=sum(ivs)/len(ivs) if ivs else None
        iv_change=((current_iv-initial_iv)/initial_iv) if initial_iv and current_iv is not None else None
        return {"underlying_price":_float(current.get("close")),"underlying_high":_float(current.get("high")),"underlying_low":_float(current.get("low")),"previous_low":_float(previous.get("low")),"previous_high":_float(previous.get("high")),"option_mark":abs(net_mark) if option_rows else _float(position.mark_json.get("mark_price")),"days_to_expiry":dte,"implied_volatility":current_iv,"iv_change_pct":iv_change,"mark":{"mark_price":abs(net_mark) if option_rows else _float(position.mark_json.get("mark_price"),0),"quantity":qty,"market_value":market_value,"unrealized_pnl":upnl,"unrealized_return_pct":ret,"delta":delta,"gamma":gamma,"theta":theta,"vega":vega,"days_to_expiry":dte}}

    def _advance_trailing_stop(self, position, management, market, actor):
        original=_float(management.get("current_underlying_stop", management.get("underlying_stop")))
        policy=str(management.get("trailing_policy") or "").upper()
        candidate=None
        if policy == "UNDERLYING_HIGHER_LOW" and str(position.direction).upper() in {"BULLISH","CALL"}:
            candidate=_float(market.get("previous_low"))
            if candidate is not None and original is not None and candidate <= original: candidate=None
        elif policy == "UNDERLYING_LOWER_HIGH" and str(position.direction).upper() in {"BEARISH","PUT"}:
            candidate=_float(market.get("previous_high"))
            if candidate is not None and original is not None and candidate >= original: candidate=None
        elif policy == "INSTITUTIONAL_STRUCTURE_ZONE":
            # The persisted plan may supply an updated institutional structure zone.
            # When a direct zone is unavailable, use a conservative price-relative
            # candidate that only tightens risk; never loosen the original stop.
            zone=management.get("institutional_structure_zone") or {}
            price=_float(market.get("underlying_price"))
            if str(position.direction).upper() in {"BULLISH","CALL"}:
                candidate=_float(zone.get("low")) if isinstance(zone,dict) else None
                if candidate is None and price is not None:candidate=price*0.9925
                if original is not None and candidate is not None and candidate<=original:candidate=None
            else:
                candidate=_float(zone.get("high")) if isinstance(zone,dict) else None
                if candidate is None and price is not None:candidate=price*1.0075
                if original is not None and candidate is not None and candidate>=original:candidate=None
        if candidate is None:return original,False
        management["current_underlying_stop"]=round(candidate,4)
        management["trailing_stop_updated_at"]=utc_now()
        self._event(position,"DYNAMIC_STOP_ADVANCED",actor,"Advanced stop using governed market structure",{"previous_stop":original,"new_stop":candidate,"policy":policy})
        for instruction in self._instructions(position.position_id):
            payload=dict(instruction.payload or {})
            if payload.get("label")=="STRUCTURAL_STOP" and instruction.status=="ARMED":
                payload["trigger_value"]=round(candidate,4);payload["updated_at"]=utc_now();instruction.payload=payload
        return round(candidate,4),True

    def _triggered(self, position, payload, market, current_stop):
        typ=payload.get("trigger_type"); value=payload.get("trigger_value"); direction=str(position.direction).upper()
        price=_float(market.get("underlying_price")); ret=_float(market.get("mark",{}).get("unrealized_return_pct"),0) or 0
        if typ=="UNDERLYING_PRICE":
            label=payload.get("label","")
            trigger=_float(current_stop if label=="STRUCTURAL_STOP" else value)
            if price is None or trigger is None:return False
            if label=="STRUCTURAL_STOP":return price<=trigger if direction in {"BULLISH","CALL"} else price>=trigger
            return price>=trigger if direction in {"BULLISH","CALL"} else price<=trigger
        if typ=="OPTION_LOSS_PCT":return ret <= -abs((_float(value,0) or 0)*100)
        if typ=="EXPIRATION_GUARD_DATE":
            try:
                exit_date=date.fromisoformat(str(value)[:10])
            except Exception:
                return False
            return datetime.now(ZoneInfo("America/New_York")).date() >= exit_date
        if typ=="DTE":return market.get("days_to_expiry") is not None and market["days_to_expiry"]<=int(value)
        if typ=="SHORT_LEG_DTE":return market.get("short_leg_dte") is not None and market["short_leg_dte"]<=int(value)
        if typ=="VOLATILITY_RULE":
            return market.get("iv_change_pct") is not None and market["iv_change_pct"]<=-0.25 and self._thesis_integrity(position,market)<0.60
        return False

    def _govern_instruction(self, position, instruction, mode, actor):
        payload=dict(instruction.payload or {})
        payload["triggered_at"]=utc_now();payload["trigger_observation"]={"position_version":position.version}
        if mode is AutomationMode.ADVISORY:status="TRIGGERED_ADVISORY"
        elif mode is AutomationMode.SEMI_AUTOMATIC:status="PENDING_APPROVAL"
        else:status="READY_FOR_AUTOMATIC_SUBMISSION"
        instruction.status=status;instruction.payload=payload
        self._event(position,"EXIT_RULE_TRIGGERED",actor,f"{payload.get('label')} triggered in {mode.value} mode",{"instruction_id":instruction.instruction_id,"status":status})
        return status

    def _ensure_canonical_exit_order(self, position, instruction, request, legs_json):
        """Durably materialize the canonical exit order before any broker transmission.

        Recovered/re-armed positions can legitimately have a fresh exit instruction
        without a pre-existing canonical order.  The IBKR routing service intentionally
        refuses to transmit in that condition.  Materializing here preserves the same
        persist-before-transmit invariant used by entry routing and makes retries
        idempotent by deterministic aggregate/client order ids.
        """
        session_factory = __import__('trading_ai.database.session', fromlist=['SessionLocal']).SessionLocal
        aggregate_id = str(request.aggregate_id)
        client_order_id = str(request.client_order_id)
        s = session_factory()
        try:
            existing = s.get(CanonicalOrderModel, aggregate_id)
            if existing is not None:
                return {
                    'aggregate_id': aggregate_id,
                    'client_order_id': existing.client_order_id,
                    'created': False,
                    'state': existing.state,
                    'durable_before_transmit': True,
                    'source': 'EXISTING_CANONICAL_EXIT_ORDER',
                }
            ts = utc_now()
            canonical = CanonicalOrderModel(
                aggregate_id=aggregate_id,
                client_order_id=client_order_id,
                account_id=position.portfolio_id,
                idempotency_key=aggregate_id,
                order_type=str(request.order_type).upper(),
                time_in_force=str(request.time_in_force).upper(),
                state='VALIDATED',
                version=1,
                total_quantity=float(request.quantity),
                filled_quantity=0.0,
                remaining_quantity=float(request.quantity),
                average_fill_price=None,
                limit_price=_float(getattr(request, 'limit_price', None)),
                stop_price=_float(getattr(request, 'stop_price', None)),
                outside_regular_hours=bool(getattr(request, 'outside_regular_hours', False)),
                strategy_name=position.strategy,
                broker_order_id=None,
                parent_aggregate_id=None,
                root_aggregate_id=aggregate_id,
                replace_count=0,
                legs_json=list(legs_json or []),
                created_at=ts,
                updated_at=ts,
                terminal_at=None,
                last_event_id=None,
                metadata_json={
                    'paper_only': True,
                    'managed_position_id': position.position_id,
                    'trade_plan_id': position.trade_plan_id,
                    'execution_intent_id': position.execution_id,
                    'exit_instruction_id': instruction.instruction_id,
                    'exit_action': instruction.action,
                    'exit_label': dict(instruction.payload or {}).get('label'),
                    'exit_execution_scope': dict(instruction.payload or {}).get('execution_scope'),
                    'exit_method': dict(instruction.payload or {}).get('exit_method'),
                    'canonical_exit_materialization': 'M74.13.1',
                    'unified_exit_materialization_version': self.M74_14_VERSION,
                    'durable_before_transmit': True,
                },
            )
            s.add(canonical)
            s.commit()
            return {
                'aggregate_id': aggregate_id,
                'client_order_id': client_order_id,
                'created': True,
                'state': 'VALIDATED',
                'durable_before_transmit': True,
                'source': 'M74_13_1_SELF_HEALING_MATERIALIZATION',
            }
        except IntegrityError:
            # A concurrent management cycle may have won the deterministic insert.
            # Treat that as successful idempotent materialization only when the exact
            # aggregate now exists; otherwise preserve the database failure.
            s.rollback()
            existing = s.get(CanonicalOrderModel, aggregate_id)
            if existing is None:
                raise
            return {
                'aggregate_id': aggregate_id,
                'client_order_id': existing.client_order_id,
                'created': False,
                'state': existing.state,
                'durable_before_transmit': True,
                'source': 'CONCURRENT_CANONICAL_EXIT_ORDER',
            }
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    @staticmethod
    def _submit_strategy_combo(service, request):
        # M74.10 strategy-level routing contract: one atomic BAG submission.
        return service.submit_combo(request)

    def _submit_exit(self, position, instruction, actor):
        if position.metadata_json.get("paper_only") is not True:
            raise ValueError("Phase 10 automatic execution is restricted to paper-managed positions")
        tp=self.s.get(TradePlanModel,position.trade_plan_id)
        intent=self.s.scalar(select(ExecutionIntentModel).where(ExecutionIntentModel.execution_intent_id==position.execution_id)) if position.execution_id else None
        if not tp or not intent:raise ValueError("Trade plan and execution intent are required for automated exit")
        binding=self.s.scalar(select(BrokerAccountBindingModel).where(BrokerAccountBindingModel.portfolio_id==position.portfolio_id,BrokerAccountBindingModel.broker_name=='INTERACTIVE_BROKERS'))
        if not binding:raise KeyError("IBKR binding not found")
        close_qty=max(1,int(instruction.quantity)); legs=list(tp.legs_json or [])
        aggregate=f"M62-EXIT-{instruction.instruction_id}";client=f"M62-EXIT-CLIENT-{instruction.instruction_id}"
        transport=IbapiPaperOrderTransport();service=IbkrPaperOrderService(lambda:__import__('trading_ai.database.session',fromlist=['SessionLocal']).SessionLocal(),transport)
        try:
            transport.connect(IbkrPaperConnectionConfig(host=binding.host,port=binding.port,client_id=binding.client_id,environment='PAPER',expected_account_id=binding.broker_account_id,timeout_seconds=15,read_only=False))
            if len(legs)==1:
                leg=legs[0]; resolved=transport.resolve_option_contract(symbol=position.symbol,expiry=str(leg['expiry']),strike=float(leg['strike']),right=str(leg['option_right']),currency=binding.base_currency or 'USD',exchange='SMART',multiplier='100',local_symbol=str(leg.get('option_symbol') or ''))
                close_side='SELL' if str(leg.get('side')).upper()=='BUY' else 'BUY'
                request=IbkrPaperOrderRequest(aggregate_id=aggregate,client_order_id=client,portfolio_id=position.portfolio_id,broker_account_id=binding.broker_account_id,symbol=position.symbol,security_type='OPT',side=close_side,quantity=float(close_qty),order_type='MKT',time_in_force='DAY',currency=binding.base_currency or 'USD',exchange='SMART',contract_id=resolved.contract_id,local_symbol=resolved.local_symbol,expiry=str(leg['expiry']),strike=float(leg['strike']),right=str(leg['option_right']).upper()[0],multiplier=resolved.multiplier,metadata={'managed_position_id':position.position_id,'exit_instruction_id':instruction.instruction_id,'actor':actor,'unified_exit_materialization':True,'exit_method':'SINGLE_LEG','trigger_label':str((instruction.payload or {}).get('label') or instruction.action),'strategy_type':position.strategy})
                canonical_info=self._ensure_canonical_exit_order(position,instruction,request,[{**dict(leg),'side':close_side,'quantity':float(close_qty),'contract_id':resolved.contract_id,'local_symbol':resolved.local_symbol}])
                result=service.submit(request)
                return {**dict(result),'canonical_exit_order':canonical_info}
            resolved_legs=[]
            base=max(1,min(max(1,int(float(x.get('quantity',1)))) for x in legs))
            for leg in legs:
                resolved=transport.resolve_option_contract(symbol=position.symbol,expiry=str(leg['expiry']),strike=float(leg['strike']),right=str(leg['option_right']),currency=binding.base_currency or 'USD',exchange='SMART',multiplier='100',local_symbol=str(leg.get('option_symbol') or ''))
                original=str(leg.get('side')).upper();close_action='SELL' if original=='BUY' else 'BUY'
                resolved_legs.append(IbkrPaperComboLegRequest(contract_id=resolved.contract_id,ratio=max(1,int(round(float(leg.get('quantity',1))/base))),action=close_action,exchange=resolved.exchange,symbol=position.symbol,local_symbol=resolved.local_symbol,expiry=str(leg['expiry']),strike=float(leg['strike']),right=str(leg['option_right']).upper(),multiplier=resolved.multiplier))
            request=IbkrPaperComboOrderRequest(aggregate_id=aggregate,client_order_id=client,portfolio_id=position.portfolio_id,broker_account_id=binding.broker_account_id,symbol=position.symbol,quantity=float(close_qty),combo_legs=tuple(resolved_legs),order_type='LMT',time_in_force='DAY',limit_price=round(-float(position.mark_json.get('mark_price') or 0.01),4),currency=binding.base_currency or 'USD',exchange='SMART',metadata={'managed_position_id':position.position_id,'exit_instruction_id':instruction.instruction_id,'actor':actor,'closing_combo':True,'strategy_level_exit':True,'includes_short_legs':True,'exit_method':'ATOMIC_BAG','trigger_label':str((instruction.payload or {}).get('label') or instruction.action),'strategy_type':position.strategy,'unified_exit_materialization':True})
            canonical_legs=[{
                'contract_id':x.contract_id,
                'ratio':x.ratio,
                'side':x.action,
                'exchange':x.exchange,
                'symbol':x.symbol,
                'local_symbol':x.local_symbol,
                'expiry':x.expiry,
                'strike':x.strike,
                'option_right':x.right,
                'multiplier':x.multiplier,
            } for x in resolved_legs]
            canonical_info=self._ensure_canonical_exit_order(position,instruction,request,canonical_legs)
            result=self._submit_strategy_combo(service,request)
            return {**dict(result),'canonical_exit_order':canonical_info}
        finally:transport.disconnect()

    def _health(self, position, market, stop):
        integrity=self._thesis_integrity(position,market);price=market.get("underlying_price");distance=None
        if price is not None and stop is not None:distance=abs(price-stop)/max(abs(price),1)*100
        score=max(0,min(100,integrity*70 + min(30,(distance or 0)*3)))
        alerts=[]
        if integrity<0.60:alerts.append("Thesis integrity is deteriorating")
        if market.get("days_to_expiry") is not None and market["days_to_expiry"]<=7:alerts.append("Expiration risk is elevated")
        return {"score":round(score,2),"direction":"DETERIORATING" if integrity<0.60 else "STABLE","confidence":round(integrity,4),"thesis_integrity":round(integrity,4),"current_stop":stop,"underlying_price":price,"alerts":alerts,"drivers":[{"category":"THESIS","score":round(integrity*100,2),"direction":"UP" if integrity>=.75 else "DOWN","contribution":round(integrity*70,2),"reason":"Live thesis-integrity composite"}]}

    def _thesis_integrity(self, position, market):
        base=_float(position.health_json.get("thesis_integrity"),_float(position.health_json.get("confidence"),.80)) or .80
        ret=_float(market.get("mark",{}).get("unrealized_return_pct"),0) or 0
        dte=market.get("days_to_expiry")
        value=base + max(-.25,min(.15,ret/200))
        if dte is not None and dte<=5:value-=.10
        if market.get("iv_change_pct") is not None and market["iv_change_pct"]<=-.25:value-=.10
        return max(0,min(1,value))

    @staticmethod
    def _decision(triggered,health):
        if triggered:
            close=any(x.get("action")=="CLOSE" for x in triggered)
            return {"action":"CLOSE" if close else "SCALE_OUT","confidence":.95,"priority":"CRITICAL" if close else "HIGH","reason":"One or more governed dynamic exit rules triggered","expected_benefit":"Enforces the persisted management plan","risk_impact":"REDUCES_RISK","alternatives":["HOLD"]}
        return {"action":"HOLD","confidence":health["confidence"],"priority":"LOW","reason":"No dynamic exit trigger is active","expected_benefit":"Preserves thesis participation","risk_impact":"MAINTAINS_RISK","alternatives":["SCALE_OUT","CLOSE"]}

    def _instructions(self,position_id):return list(self.s.scalars(select(PositionExitInstructionModel).where(PositionExitInstructionModel.position_id==position_id).order_by(PositionExitInstructionModel.id)))
    @staticmethod
    def _next_target(direction,targets,price):
        if price is None:return targets[0] if targets else None
        if str(direction).upper() in {"BULLISH","CALL"}:return next((x for x in sorted(targets) if x>price),None)
        return next((x for x in sorted(targets,reverse=True) if x<price),None)
    def _event(self,row,event,actor,reason,payload):self.s.add(PositionEventModel(event_id=f"PE-{uuid4().hex.upper()}",position_id=row.position_id,position_version=row.version,event_type=event,actor=actor,reason=reason,event_timestamp=utc_now(),payload_json=payload))
    @staticmethod
    def _instruction_payload(x):return {"instruction_id":x.instruction_id,"assessment_id":x.assessment_id,"position_id":x.position_id,"action":x.action,"quantity":x.quantity,"status":x.status,"payload":dict(x.payload or {}),"created_at":x.created_at}
    @staticmethod
    def _position_payload(x):return {"position_id":x.position_id,"version":x.version,"state":x.state,"metadata":dict(x.metadata_json or {})}

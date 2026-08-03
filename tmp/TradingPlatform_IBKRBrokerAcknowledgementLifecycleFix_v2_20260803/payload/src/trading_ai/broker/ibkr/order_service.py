from __future__ import annotations
import hashlib
from datetime import datetime, timezone
from typing import Callable
from sqlalchemy import func, select
from trading_ai.authoritative_paper_trading.database_models import CanonicalOrderModel
from .database_models import BrokerAccountBindingModel, BrokerExecutionModel, BrokerOrderControlModel, BrokerOrderModel
from .order_models import IbkrPaperExecution, IbkrPaperOrderRequest, IbkrPaperOrderStatus

def _now() -> str: return datetime.now(timezone.utc).isoformat()
def _stable_id(prefix: str, *parts: object) -> str:
    return f"{prefix}-{hashlib.sha256('|'.join(map(str, parts)).encode()).hexdigest()[:24].upper()}"

class IbkrPaperOrderGovernanceService:
    def __init__(self, session_factory: Callable): self.session_factory = session_factory
    @staticmethod
    def _binding(session, portfolio_id: str):
        row = session.scalar(select(BrokerAccountBindingModel).where(BrokerAccountBindingModel.portfolio_id == portfolio_id, BrokerAccountBindingModel.broker_name == "INTERACTIVE_BROKERS"))
        if row is None: raise KeyError(f"IBKR binding not found for {portfolio_id}")
        return row
    def activate(self, portfolio_id: str, *, confirmation: str, activated_by: str = "operator") -> dict:
        expected = f"ENABLE IBKR PAPER ORDERS {portfolio_id}"
        if confirmation.strip() != expected: raise ValueError(f"confirmation must exactly equal: {expected}")
        s = self.session_factory()
        try:
            binding = self._binding(s, portfolio_id)
            if binding.status != "VERIFIED_READ_ONLY": raise ValueError("binding must be VERIFIED_READ_ONLY")
            if binding.live_trading_enabled or binding.broker_environment != "PAPER": raise ValueError("only paper bindings may be activated")
            now = _now(); control = s.get(BrokerOrderControlModel, portfolio_id)
            if control is None:
                control = BrokerOrderControlModel(portfolio_id=portfolio_id, paper_order_submission_enabled=True, activation_token_hash=hashlib.sha256(confirmation.encode()).hexdigest(), activated_at=now, activated_by=activated_by, version=1, updated_at=now, metadata_json={"paper_only": True, "live_trading_enabled": False}); s.add(control)
            else:
                control.paper_order_submission_enabled=True; control.activation_token_hash=hashlib.sha256(confirmation.encode()).hexdigest(); control.activated_at=now; control.activated_by=activated_by; control.disabled_at=None; control.disable_reason=""; control.version += 1; control.updated_at=now
            binding.status="VERIFIED_PAPER_TRADING"; binding.read_only=False; binding.updated_at=now
            s.commit()
        except Exception: s.rollback(); raise
        finally: s.close()
        return self.status(portfolio_id)
    def disable(self, portfolio_id: str, *, reason: str) -> dict:
        s=self.session_factory()
        try:
            binding=self._binding(s, portfolio_id); now=_now(); control=s.get(BrokerOrderControlModel, portfolio_id)
            if control is None:
                control=BrokerOrderControlModel(portfolio_id=portfolio_id,paper_order_submission_enabled=False,activation_token_hash="",activated_by="",disabled_at=now,disable_reason=reason,version=1,updated_at=now,metadata_json={"paper_only":True}); s.add(control)
            else:
                control.paper_order_submission_enabled=False; control.disabled_at=now; control.disable_reason=reason; control.version += 1; control.updated_at=now
            binding.status="VERIFIED_READ_ONLY"; binding.read_only=True; binding.updated_at=now; s.commit()
        except Exception: s.rollback(); raise
        finally: s.close()
        return self.status(portfolio_id)
    def status(self, portfolio_id: str) -> dict:
        s=self.session_factory()
        try:
            binding=self._binding(s,portfolio_id); control=s.get(BrokerOrderControlModel,portfolio_id); enabled=bool(control and control.paper_order_submission_enabled)
            return {"portfolio_id":portfolio_id,"binding_status":binding.status,"environment":binding.broker_environment,"paper_order_submission_enabled":enabled,"live_trading_enabled":bool(binding.live_trading_enabled),"read_only":bool(binding.read_only),"status":"PAPER_ORDER_ROUTING_ENABLED" if enabled else "PAPER_ORDER_ROUTING_DISABLED"}
        finally: s.close()

class IbkrPaperOrderService:
    def __init__(self, session_factory: Callable, transport): self.session_factory=session_factory; self.transport=transport
    def _require_enabled(self, s, portfolio_id: str):
        binding=IbkrPaperOrderGovernanceService._binding(s,portfolio_id); control=s.get(BrokerOrderControlModel,portfolio_id)
        if binding.broker_environment != "PAPER" or binding.live_trading_enabled: raise ValueError("only IBKR paper bindings are supported")
        if binding.status != "VERIFIED_PAPER_TRADING" or binding.read_only: raise PermissionError("IBKR binding is not paper-order enabled")
        if control is None or not control.paper_order_submission_enabled: raise PermissionError("paper order submission control is disabled")
        return binding
    def submit(self, request: IbkrPaperOrderRequest) -> dict:
        request.validate(); s=self.session_factory()
        try:
            binding=self._require_enabled(s,request.portfolio_id)
            if binding.broker_account_id != request.broker_account_id.upper(): raise ValueError("broker account mismatch")
            canonical=s.get(CanonicalOrderModel,request.aggregate_id)
            if canonical is None: raise KeyError(f"canonical order not found: {request.aggregate_id}")
            existing=s.scalar(select(BrokerOrderModel).where(BrokerOrderModel.binding_id==binding.binding_id,BrokerOrderModel.aggregate_id==request.aggregate_id))
            if existing is not None: return self._dict(existing,True)
            health=self.transport.health(); managed={str(v).upper() for v in health.get("managed_accounts",())}
            if request.broker_account_id.upper() not in managed: raise RuntimeError("connected session does not expose registered paper account")

            # IBKR's nextValidId can move backward after a paper-account reset,
            # client-id change, or gateway restart. Keep the transport cursor above
            # every broker order id already persisted for this binding.
            maximum_persisted_order_id = s.scalar(
                select(func.max(BrokerOrderModel.broker_order_id)).where(
                    BrokerOrderModel.binding_id == binding.binding_id
                )
            )
            minimum_order_id = int(maximum_persisted_order_id or 0) + 1
            set_floor = getattr(self.transport, "set_order_id_floor", None)
            if callable(set_floor):
                set_floor(minimum_order_id)

            broker_order_id=int(self.transport.submit_order(request))
            wait_for_ack = getattr(self.transport, "wait_for_order_acknowledgement", None)
            acknowledgement = wait_for_ack(broker_order_id) if callable(wait_for_ack) else {"acknowledged": False, "callback": "UNAVAILABLE", "status": "AWAITING_BROKER_ACK"}
            now=_now()

            collision=s.scalar(select(BrokerOrderModel).where(
                BrokerOrderModel.binding_id==binding.binding_id,
                BrokerOrderModel.broker_order_id==broker_order_id,
            ))
            if collision is not None:
                # The broker has already accepted the order. Cancel it immediately
                # rather than allowing an untracked paper order to remain working.
                try:
                    self.transport.cancel_order(broker_order_id)
                except Exception:
                    pass
                raise RuntimeError(
                    "IBKR returned a broker order id that is already persisted "
                    f"for this binding: {broker_order_id}; cancellation requested"
                )

            row=BrokerOrderModel(broker_order_record_id=_stable_id("IBKR-ORD",binding.binding_id,broker_order_id),binding_id=binding.binding_id,portfolio_id=request.portfolio_id,aggregate_id=request.aggregate_id,client_order_id=request.client_order_id,broker_account_id=request.broker_account_id.upper(),broker_order_id=broker_order_id,permanent_id=0,api_client_id=binding.client_id,symbol=request.symbol,security_type=request.security_type,side=request.side.upper(),quantity=request.quantity,order_type=request.order_type.upper(),time_in_force=request.time_in_force.upper(),limit_price=request.limit_price,stop_price=request.stop_price,status=str(acknowledgement.get("status") or "AWAITING_BROKER_ACK"),filled_quantity=float(acknowledgement.get("filled_quantity",0.0) or 0.0),remaining_quantity=float(acknowledgement.get("remaining_quantity",request.quantity) if acknowledgement.get("remaining_quantity") is not None else request.quantity),average_fill_price=float(acknowledgement.get("average_fill_price",0.0) or 0.0),submitted_at=now,updated_at=now,last_error=str(acknowledgement.get("error_message") or ""),raw_json={"request":request.__dict__,"paper_only":True,"broker_acknowledgement":acknowledgement}); s.add(row)
            canonical.broker_order_id=str(broker_order_id); canonical.state="SUBMITTED"; canonical.updated_at=now; canonical.metadata_json={**(canonical.metadata_json or {}),"broker":"INTERACTIVE_BROKERS","environment":"PAPER"}
            s.commit(); return self._dict(row,False)
        except Exception: s.rollback(); raise
        finally: s.close()
    def submit_combo(self, request: IbkrPaperComboOrderRequest) -> dict:
        request.validate()
        s = self.session_factory()
        try:
            binding = self._require_enabled(s, request.portfolio_id)
            if binding.broker_account_id != request.broker_account_id.upper():
                raise ValueError("broker account mismatch")
            canonical = s.get(CanonicalOrderModel, request.aggregate_id)
            if canonical is None:
                raise KeyError(f"canonical order not found: {request.aggregate_id}")
            existing = s.scalar(select(BrokerOrderModel).where(
                BrokerOrderModel.binding_id == binding.binding_id,
                BrokerOrderModel.aggregate_id == request.aggregate_id,
            ))
            if existing is not None:
                return self._dict(existing, True)
            health = self.transport.health()
            managed = {str(v).upper() for v in health.get("managed_accounts", ())}
            if request.broker_account_id.upper() not in managed:
                raise RuntimeError("connected session does not expose registered paper account")
            maximum_persisted_order_id = s.scalar(select(func.max(BrokerOrderModel.broker_order_id)).where(BrokerOrderModel.binding_id == binding.binding_id))
            set_floor = getattr(self.transport, "set_order_id_floor", None)
            if callable(set_floor):
                set_floor(int(maximum_persisted_order_id or 0) + 1)
            broker_order_id = int(self.transport.submit_combo_order(request))
            wait_for_ack = getattr(self.transport, "wait_for_order_acknowledgement", None)
            acknowledgement = wait_for_ack(broker_order_id) if callable(wait_for_ack) else {"acknowledged": False, "callback": "UNAVAILABLE", "status": "AWAITING_BROKER_ACK"}
            now = _now()
            collision = s.scalar(select(BrokerOrderModel).where(
                BrokerOrderModel.binding_id == binding.binding_id,
                BrokerOrderModel.broker_order_id == broker_order_id,
            ))
            if collision is not None:
                try:
                    self.transport.cancel_order(broker_order_id)
                except Exception:
                    pass
                raise RuntimeError(f"IBKR returned a duplicate broker order id: {broker_order_id}; cancellation requested")
            raw_request = {
                **request.__dict__,
                "combo_legs": [leg.__dict__ for leg in request.combo_legs],
            }
            row = BrokerOrderModel(
                broker_order_record_id=_stable_id("IBKR-ORD", binding.binding_id, broker_order_id),
                binding_id=binding.binding_id,
                portfolio_id=request.portfolio_id,
                aggregate_id=request.aggregate_id,
                client_order_id=request.client_order_id,
                broker_account_id=request.broker_account_id.upper(),
                broker_order_id=broker_order_id,
                permanent_id=int(acknowledgement.get("permanent_id", 0) or 0),
                api_client_id=binding.client_id,
                symbol=request.symbol,
                security_type="BAG",
                side=request.side,
                quantity=request.quantity,
                order_type=request.order_type.upper(),
                time_in_force=request.time_in_force.upper(),
                limit_price=request.limit_price,
                stop_price=None,
                status=str(acknowledgement.get("status") or "AWAITING_BROKER_ACK"),
                filled_quantity=float(acknowledgement.get("filled_quantity", 0.0) or 0.0),
                remaining_quantity=float(acknowledgement.get("remaining_quantity", request.quantity) if acknowledgement.get("remaining_quantity") is not None else request.quantity),
                average_fill_price=float(acknowledgement.get("average_fill_price", 0.0) or 0.0),
                submitted_at=now,
                updated_at=now,
                last_error=str(acknowledgement.get("error_message") or ""),
                raw_json={"request": raw_request, "paper_only": True, "atomic_combo": True, "broker_acknowledgement": acknowledgement},
            )
            s.add(row)
            canonical.broker_order_id = str(broker_order_id)
            canonical.state = "SUBMITTED"
            canonical.updated_at = now
            canonical.metadata_json = {
                **(canonical.metadata_json or {}),
                "broker": "INTERACTIVE_BROKERS",
                "environment": "PAPER",
                "security_type": "BAG",
                "atomic_combo": True,
                "broker_acknowledgement": acknowledgement,
            }
            s.commit()
            return self._dict(row, False)
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    def cancel(self, portfolio_id: str, aggregate_id: str) -> dict:
        s=self.session_factory()
        try:
            self._require_enabled(s,portfolio_id); row=s.scalar(select(BrokerOrderModel).where(BrokerOrderModel.portfolio_id==portfolio_id,BrokerOrderModel.aggregate_id==aggregate_id))
            if row is None: raise KeyError(f"broker order not found for {aggregate_id}")
            self.transport.cancel_order(row.broker_order_id); row.status="CANCEL_REQUESTED"; row.updated_at=_now(); s.commit(); return self._dict(row,False)
        except Exception: s.rollback(); raise
        finally: s.close()
    def synchronize(self, portfolio_id: str) -> dict:
        s=self.session_factory()
        try:
            binding=IbkrPaperOrderGovernanceService._binding(s,portfolio_id); updated=0; imported=0
            for status in self.transport.order_statuses(binding.broker_account_id):
                row=s.scalar(select(BrokerOrderModel).where(BrokerOrderModel.binding_id==binding.binding_id,BrokerOrderModel.broker_order_id==status.broker_order_id))
                if row is None: continue
                row.permanent_id=status.permanent_id; row.status=status.status.upper(); row.filled_quantity=status.filled_quantity; row.remaining_quantity=status.remaining_quantity; row.average_fill_price=status.average_fill_price; row.updated_at=status.updated_at; row.raw_json={**(row.raw_json or {}),"last_status":status.raw}
                canonical=s.get(CanonicalOrderModel,row.aggregate_id)
                if canonical is not None:
                    canonical_state=self._canonical_state(status.status)
                    canonical.state=canonical_state
                    canonical.filled_quantity=status.filled_quantity
                    canonical.remaining_quantity=status.remaining_quantity
                    canonical.average_fill_price=status.average_fill_price or None
                    canonical.broker_order_id=str(status.broker_order_id)
                    canonical.updated_at=status.updated_at
                    if canonical_state in {"FILLED","CANCELED","REJECTED"}:
                        canonical.terminal_at=canonical.terminal_at or status.updated_at
                updated += 1
            for ex in self.transport.executions(binding.broker_account_id):
                if s.get(BrokerExecutionModel,ex.execution_id) is not None: continue
                order=s.scalar(select(BrokerOrderModel).where(BrokerOrderModel.binding_id==binding.binding_id,BrokerOrderModel.broker_order_id==ex.broker_order_id))
                if order is None: continue
                s.add(BrokerExecutionModel(execution_id=ex.execution_id,broker_order_record_id=order.broker_order_record_id,binding_id=binding.binding_id,portfolio_id=portfolio_id,aggregate_id=order.aggregate_id,broker_account_id=ex.broker_account_id,broker_order_id=ex.broker_order_id,permanent_id=ex.permanent_id,contract_id=ex.contract_id,symbol=ex.symbol,security_type=ex.security_type,side=ex.side,quantity=ex.quantity,price=ex.price,commission=ex.commission,currency=ex.currency,exchange=ex.exchange,executed_at=ex.executed_at,imported_at=_now(),settled=False,raw_json=ex.raw)); imported += 1
            s.commit(); return {"portfolio_id":portfolio_id,"orders_updated":updated,"executions_imported":imported,"status":"SYNCHRONIZED"}
        except Exception: s.rollback(); raise
        finally: s.close()
    @staticmethod
    def _canonical_state(status: str) -> str:
        value=status.upper().replace(" ","")
        if value=="FILLED": return "FILLED"
        if value in {"CANCELLED","CANCELED","APICANCELLED","PENDINGCANCEL"}: return "CANCELED"
        if value in {"INACTIVE","REJECTED"}: return "REJECTED"
        return "SUBMITTED"
    @staticmethod
    def _dict(row, replayed: bool) -> dict:
        return {"portfolio_id":row.portfolio_id,"aggregate_id":row.aggregate_id,"client_order_id":row.client_order_id,"broker_order_id":row.broker_order_id,"permanent_id":row.permanent_id,"status":row.status,"filled_quantity":row.filled_quantity,"remaining_quantity":row.remaining_quantity,"average_fill_price":row.average_fill_price,"last_error":row.last_error,"broker_acknowledgement":(row.raw_json or {}).get("broker_acknowledgement"),"replayed":replayed,"environment":"PAPER","live_trading_enabled":False}

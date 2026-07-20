from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

from trading_ai.ui.models.paper_commands import PaperOrderSubmitRequest
from trading_ai.ui.models.professional_order_entry import (
    ApprovalRequest,
    StrategyRiskPreview,
    StrategyTicketRecord,
    StrategyTicketRequest,
    SubmissionRequest,
)
from trading_ai.ui.services.paper_command_service import PaperCommandService


class ProfessionalOrderEntryService:
    def __init__(
        self,
        state_path: str | Path = "reports/ui/professional_order_tickets.json",
        paper_service: PaperCommandService | None = None,
    ) -> None:
        self.state_path = Path(state_path)
        self.paper_service = paper_service or PaperCommandService()
        self._lock = RLock()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    def _load(self):
        if not self.state_path.exists():
            return []
        return [
            StrategyTicketRecord.model_validate(item)
            for item in json.loads(self.state_path.read_text(encoding="utf-8"))
        ]

    def _save(self, records):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.state_path.with_suffix(".tmp")
        temp.write_text(
            json.dumps([item.model_dump(mode="json") for item in records], indent=2),
            encoding="utf-8",
        )
        temp.replace(self.state_path)

    @staticmethod
    def _classify(request: StrategyTicketRequest) -> str:
        legs = request.legs
        if len(legs) == 1:
            return "LONG_OPTION" if legs[0].side == "BUY" else "SHORT_OPTION"
        if len(legs) == 2:
            types = {leg.option_type for leg in legs}
            sides = {leg.side for leg in legs}
            if len(types) == 1 and sides == {"BUY", "SELL"}:
                return "VERTICAL_SPREAD"
            if len(types) == 2 and all(leg.side == "BUY" for leg in legs):
                return "LONG_STRADDLE_OR_STRANGLE"
            if len(types) == 2 and all(leg.side == "SELL" for leg in legs):
                return "SHORT_STRADDLE_OR_STRANGLE"
        if len(legs) == 4:
            return "IRON_CONDOR_OR_BUTTERFLY"
        return "CUSTOM_MULTI_LEG"

    def preview(self, request: StrategyTicketRequest) -> StrategyRiskPreview:
        multiplier = 100
        contracts = request.contracts
        mids = [
            ((leg.bid + leg.ask) / 2 if leg.ask > 0 else max(leg.bid, leg.ask))
            for leg in request.legs
        ]
        signed = [
            mid * leg.ratio * (1 if leg.side == "BUY" else -1)
            for mid, leg in zip(mids, request.legs)
        ]
        net_debit = sum(signed)
        commission = sum(leg.ratio for leg in request.legs) * contracts * request.commission_per_contract
        strikes = sorted({leg.option_strike for leg in request.legs})
        strategy_type = self._classify(request)
        bounded = all(leg.side == "BUY" for leg in request.legs) or strategy_type in {
            "VERTICAL_SPREAD", "IRON_CONDOR_OR_BUTTERFLY"
        }
        warnings = []
        max_loss = None
        max_profit = None
        margin = 0.0
        breakevens = []

        if net_debit >= 0:
            max_loss = net_debit * multiplier * contracts + commission
            margin = max_loss
        elif bounded and len(strikes) >= 2:
            width = max(strikes) - min(strikes)
            credit = abs(net_debit) * multiplier * contracts
            max_loss = max(0.0, width * multiplier * contracts - credit + commission)
            max_profit = max(0.0, credit - commission)
            margin = max_loss
        else:
            margin = request.underlying_price * multiplier * contracts * 0.20
            warnings.append("Unbounded or path-dependent risk estimate; broker margin may be higher.")

        if len(request.legs) == 1:
            leg = request.legs[0]
            premium = mids[0]
            breakevens = [
                leg.option_strike + premium if leg.option_type == "CALL"
                else leg.option_strike - premium
            ]
            if leg.side == "BUY":
                max_profit = None if leg.option_type == "CALL" else max(
                    0.0, leg.option_strike * multiplier * contracts - (max_loss or 0)
                )
        elif len(strikes) == 2 and strategy_type == "VERTICAL_SPREAD":
            breakevens = [min(strikes) + abs(net_debit)]

        risk_budget = request.account_equity * request.max_risk_pct
        per_contract_risk = (max_loss / contracts) if max_loss is not None else margin / contracts
        recommended = max(0, int(risk_budget // per_contract_risk)) if per_contract_risk > 0 else contracts
        recommended = min(recommended, 1000)
        utilization = (
            ((max_loss or margin) / risk_budget * 100.0) if risk_budget > 0 else None
        )
        if contracts > recommended:
            warnings.append("Requested contracts exceed the configured risk-budget recommendation.")
        if request.environment != "PAPER":
            warnings.append("Simulation mode selected; live trading remains unavailable.")

        return StrategyRiskPreview(
            strategy_type=strategy_type,
            contracts_requested=contracts,
            contracts_recommended=recommended,
            net_debit_credit=net_debit,
            estimated_commission=commission,
            estimated_margin=margin,
            maximum_loss=max_loss,
            maximum_profit=max_profit,
            breakevens=breakevens,
            net_delta=sum((1 if l.side == "BUY" else -1) * l.delta * l.ratio * contracts for l in request.legs),
            net_gamma=sum((1 if l.side == "BUY" else -1) * l.gamma * l.ratio * contracts for l in request.legs),
            net_theta=sum((1 if l.side == "BUY" else -1) * l.theta * l.ratio * contracts for l in request.legs),
            net_vega=sum((1 if l.side == "BUY" else -1) * l.vega * l.ratio * contracts for l in request.legs),
            risk_budget=risk_budget,
            risk_budget_utilization_pct=utilization,
            bounded_risk=bounded,
            warnings=warnings,
        )

    def create(self, request: StrategyTicketRequest):
        with self._lock:
            preview = self.preview(request)
            now = self._now()
            record = StrategyTicketRecord(
                ticket_id=f"ticket-{uuid4().hex[:16]}",
                created_at=now,
                updated_at=now,
                status="PENDING_APPROVAL",
                request=request,
                preview=preview,
                requester_user_id=request.actor.user_id,
            )
            records = self._load()
            records.append(record)
            self._save(records)
            return record

    def list(self):
        return sorted(self._load(), key=lambda x: x.created_at, reverse=True)

    def get(self, ticket_id):
        record = next((x for x in self._load() if x.ticket_id == ticket_id), None)
        if record is None:
            raise KeyError(ticket_id)
        return record

    def approve(self, ticket_id: str, request: ApprovalRequest):
        with self._lock:
            records = self._load()
            record = next((x for x in records if x.ticket_id == ticket_id), None)
            if record is None:
                raise KeyError(ticket_id)
            if request.actor.user_id == record.requester_user_id:
                raise PermissionError("Four-eye approval requires a different user.")
            if "paper_orders.approve" not in request.actor.permissions:
                raise PermissionError("Missing paper_orders.approve permission.")
            if not request.confirmation_token.startswith("CONFIRM-PAPER-"):
                raise PermissionError("Invalid paper approval confirmation token.")
            record.status = "APPROVED" if request.decision == "APPROVE" else "REJECTED"
            record.approver_user_id = request.actor.user_id
            record.approval_reason = request.reason
            record.updated_at = self._now()
            self._save(records)
            return record

    def submit(self, ticket_id: str, request: SubmissionRequest):
        with self._lock:
            records = self._load()
            record = next((x for x in records if x.ticket_id == ticket_id), None)
            if record is None:
                raise KeyError(ticket_id)
            if record.status != "APPROVED":
                raise PermissionError("Ticket must be approved before submission.")
            if "paper_orders.submit" not in request.actor.permissions:
                raise PermissionError("Missing paper_orders.submit permission.")
            order_ids, errors = [], []
            per_unit_net = abs(record.request.net_limit_price or record.preview.net_debit_credit)
            total_ratio = sum(leg.ratio for leg in record.request.legs)
            for index, leg in enumerate(record.request.legs):
                leg_price = (
                    (leg.ask if leg.side == "BUY" else leg.bid)
                    if record.request.order_type == "LIMIT"
                    else ((leg.bid + leg.ask) / 2 if leg.ask > 0 else leg.bid)
                )
                decision = self.paper_service.submit(
                    PaperOrderSubmitRequest(
                        environment=record.request.environment,
                        symbol=leg.symbol,
                        instrument_type="OPTION",
                        side=leg.side,
                        order_type=record.request.order_type,
                        quantity=record.request.contracts * leg.ratio,
                        limit_price=leg_price if record.request.order_type == "LIMIT" else None,
                        estimated_price=leg_price if record.request.order_type == "MARKET" else None,
                        option_expiry=leg.option_expiry,
                        option_strike=leg.option_strike,
                        option_type=leg.option_type,
                        reason=f"{record.request.reason}; strategy={record.request.strategy_name}; ticket={ticket_id}",
                        confirmation_token=request.confirmation_token,
                        idempotency_key=f"{request.idempotency_key}-leg-{index}",
                        actor=request.actor,
                    )
                )
                if decision.allowed and decision.order:
                    order_ids.append(decision.order.order_id)
                else:
                    errors.extend(decision.policy_reasons or [decision.message])
            record.submitted_order_ids = order_ids
            record.errors = errors
            record.status = "SUBMITTED" if len(order_ids) == len(record.request.legs) else "PARTIALLY_SUBMITTED"
            record.updated_at = self._now()
            self._save(records)
            return record

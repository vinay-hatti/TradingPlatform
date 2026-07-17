from __future__ import annotations
import uuid

from trading_ai.order_management.order_profile import (
    CanonicalOrderCommand,
    CanonicalOrderLeg,
)
from .paper_scan_policy import PaperScanAutomationPolicy
from .paper_scan_profile import (
    PaperDecisionPipelineResult,
    PaperOrderDraft,
    PaperScanCandidate,
)

class PaperSignalOrderMapper:
    def __init__(self, policy: PaperScanAutomationPolicy | None = None) -> None:
        self.policy = policy or PaperScanAutomationPolicy()
        self.policy.validate()

    def map(
        self,
        *,
        candidate: PaperScanCandidate,
        decision: PaperDecisionPipelineResult,
        account_id: str,
    ) -> PaperOrderDraft:
        if not decision.approved:
            raise ValueError("Cannot map a rejected candidate to an order")

        asset_class = candidate.asset_class.upper()
        side = candidate.direction.upper()
        if asset_class == "OPTION":
            side = {
                "LONG": "BUY_TO_OPEN",
                "SHORT": "SELL_TO_OPEN",
                "CALL": "BUY_TO_OPEN",
                "PUT": "BUY_TO_OPEN",
            }.get(side, side)
            multiplier = self.policy.default_option_multiplier
        else:
            side = {"LONG": "BUY", "SHORT": "SELL"}.get(side, side)
            multiplier = self.policy.default_equity_multiplier

        aggregate_id = f"paper-agg-{uuid.uuid4().hex}"
        client_order_id = f"paper-client-{uuid.uuid4().hex}"
        idempotency_key = f"paper-idem-{candidate.candidate_id}"

        leg = CanonicalOrderLeg(
            leg_id="leg-1",
            symbol=candidate.symbol,
            asset_class=asset_class,
            side=side,
            quantity=candidate.quantity,
            position_effect="OPEN",
            metadata={
                "multiplier": multiplier,
                "expiration": candidate.expiration,
                "strike": candidate.strike,
                "option_type": candidate.option_type,
                "sector": candidate.sector,
                **candidate.metadata,
            },
        )
        command = CanonicalOrderCommand(
            command_id=f"cmd-{uuid.uuid4().hex}",
            command_type="CREATE",
            aggregate_id=aggregate_id,
            client_order_id=client_order_id,
            account_id=account_id,
            idempotency_key=idempotency_key,
            order_type=candidate.order_type,
            time_in_force=candidate.time_in_force,
            legs=(leg,),
            limit_price=(
                candidate.limit_price
                if candidate.limit_price is not None
                else candidate.market_price
            ),
            stop_price=candidate.stop_price,
            strategy_name=candidate.strategy_name,
            metadata={
                "paper_candidate_id": candidate.candidate_id,
                "paper_probability": candidate.probability,
                "paper_score": candidate.score,
            },
        )
        return PaperOrderDraft(
            candidate_id=candidate.candidate_id,
            aggregate_id=aggregate_id,
            client_order_id=client_order_id,
            account_id=account_id,
            idempotency_key=idempotency_key,
            strategy_name=candidate.strategy_name,
            command=command,
            risk_metadata={
                "risk_gateway_approved": bool(
                    getattr(decision.risk_gateway_decision, "allowed", False)
                    if not isinstance(decision.risk_gateway_decision, dict)
                    else decision.risk_gateway_decision.get("allowed", False)
                ),
                "decision_probability": decision.probability,
                "decision_score": decision.score,
            },
        )

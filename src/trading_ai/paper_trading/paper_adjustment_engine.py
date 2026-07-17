from __future__ import annotations
from .paper_position_policy import PaperPositionPolicy
from .paper_position_profile import (
    PaperAdjustmentProposal,
    PaperPositionDecision,
    PaperPositionProfile,
)

class PaperAdjustmentEngine:
    def __init__(self, policy: PaperPositionPolicy | None = None) -> None:
        self.policy = policy or PaperPositionPolicy()
        self.policy.validate()

    def evaluate(
        self,
        position: PaperPositionProfile,
    ) -> PaperPositionDecision:
        if not self.policy.allow_adjustments:
            return PaperPositionDecision(
                valid=True,
                allowed=False,
                action="ADJUSTMENT_EVALUATION",
                position_id=position.position_id,
                recommendation="REJECT",
                rejection_reasons=("ADJUSTMENTS_DISABLED",),
            )
        if position.adjustment_count >= self.policy.maximum_adjustments_per_position:
            return PaperPositionDecision(
                valid=True,
                allowed=False,
                action="ADJUSTMENT_EVALUATION",
                position_id=position.position_id,
                recommendation="REJECT",
                rejection_reasons=("MAXIMUM_ADJUSTMENTS_REACHED",),
            )
        if position.unrealized_pnl >= 0:
            return PaperPositionDecision(
                valid=True,
                allowed=True,
                action="ADJUSTMENT_EVALUATION",
                position_id=position.position_id,
                recommendation="NONE",
                position=position,
            )

        proposal = PaperAdjustmentProposal(
            position_id=position.position_id,
            adjustment_type="REDUCE_SIZE",
            reason="NEGATIVE_UNREALIZED_PNL",
            quantity=max(1.0, abs(position.quantity) / 2.0),
            target_symbol=position.symbol,
            target_price=position.market_price,
        )
        return PaperPositionDecision(
            valid=True,
            allowed=True,
            action="ADJUSTMENT_EVALUATION",
            position_id=position.position_id,
            recommendation="ADJUST",
            position=position,
            adjustment=proposal,
        )

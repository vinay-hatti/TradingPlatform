from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
import uuid

from .paper_execution_profile import PaperExecutionRecord, PaperFillProfile
from .paper_position_policy import PaperPositionPolicy
from .paper_position_profile import (
    PaperExitSignal,
    PaperPositionDecision,
    PaperPositionLot,
    PaperPositionProfile,
)

def _is_buy(side: str) -> bool:
    return side.upper().startswith("BUY")

def _signed_quantity(side: str, quantity: float) -> float:
    return abs(quantity) if _is_buy(side) else -abs(quantity)

class PaperPositionEngine:
    def __init__(self, policy: PaperPositionPolicy | None = None) -> None:
        self.policy = policy or PaperPositionPolicy()
        self.policy.validate()

    def open_from_execution(
        self,
        record: PaperExecutionRecord,
        *,
        asset_class: str,
        multiplier: int,
    ) -> PaperPositionDecision:
        if not record.fills:
            return PaperPositionDecision(
                valid=True,
                allowed=False,
                action="OPEN",
                position_id=record.aggregate_id,
                recommendation="REJECT",
                rejection_reasons=("NO_FILLS",),
            )

        signed_qty = sum(_signed_quantity(f.side, f.quantity) for f in record.fills)
        total_abs_qty = sum(abs(f.quantity) for f in record.fills)
        average_cost = (
            sum(abs(f.quantity) * f.fill_price for f in record.fills)
            / total_abs_qty
        )
        lots = tuple(
            PaperPositionLot(
                lot_id=f"lot-{uuid.uuid4().hex}",
                fill_id=f.fill_id,
                quantity=_signed_quantity(f.side, f.quantity),
                price=f.fill_price,
                commission=f.commission,
                opened_at=f.filled_at,
                remaining_quantity=_signed_quantity(f.side, f.quantity),
            )
            for f in record.fills
        )
        market_price = average_cost
        cost_basis = abs(signed_qty) * average_cost * multiplier
        now = datetime.now(timezone.utc).isoformat()
        position = PaperPositionProfile(
            position_id=f"position-{record.aggregate_id}",
            session_id=record.session_id,
            account_id=record.account_id,
            aggregate_id=record.aggregate_id,
            symbol=record.fills[0].symbol,
            asset_class=asset_class.upper(),
            side="LONG" if signed_qty > 0 else "SHORT",
            quantity=signed_qty,
            average_cost=round(average_cost, 6),
            multiplier=multiplier,
            market_price=round(market_price, 6),
            market_value=round(signed_qty * market_price * multiplier, 6),
            cost_basis=round(cost_basis, 6),
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            total_commissions=round(record.commissions, 6),
            lots=lots,
            high_water_mark=market_price,
            low_water_mark=market_price,
            profit_target_pct=self.policy.default_profit_target_pct,
            stop_loss_pct=self.policy.default_stop_loss_pct,
            trailing_stop_pct=self.policy.default_trailing_stop_pct,
            opened_at=now,
            updated_at=now,
        )
        return PaperPositionDecision(
            valid=True,
            allowed=True,
            action="OPEN",
            position_id=position.position_id,
            recommendation="SAVE",
            position=position,
        )

    def mark(
        self,
        position: PaperPositionProfile,
        market_price: float,
    ) -> PaperPositionProfile:
        if self.policy.require_positive_mark_price and market_price <= 0:
            raise ValueError("market_price must be positive")
        direction = 1.0 if position.quantity > 0 else -1.0
        unrealized = (
            (market_price - position.average_cost)
            * abs(position.quantity)
            * position.multiplier
            * direction
        )
        high = max(position.high_water_mark or market_price, market_price)
        low = min(position.low_water_mark or market_price, market_price)
        return replace(
            position,
            market_price=round(market_price, 6),
            market_value=round(
                position.quantity * market_price * position.multiplier,
                6,
            ),
            unrealized_pnl=round(unrealized, 6),
            high_water_mark=round(high, 6),
            low_water_mark=round(low, 6),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

    def evaluate_exit(
        self,
        position: PaperPositionProfile,
    ) -> PaperPositionDecision:
        if not position.is_open:
            return PaperPositionDecision(
                valid=True,
                allowed=False,
                action="EXIT_EVALUATION",
                position_id=position.position_id,
                recommendation="NONE",
                rejection_reasons=("POSITION_NOT_OPEN",),
            )

        direction = 1.0 if position.quantity > 0 else -1.0
        return_pct = (
            (position.market_price - position.average_cost)
            / position.average_cost
            * direction
            if position.average_cost > 0
            else 0.0
        )

        reason = None
        trigger = 0.0
        if (
            self.policy.enable_profit_target_exit
            and position.profit_target_pct is not None
            and return_pct >= position.profit_target_pct
        ):
            reason = "PROFIT_TARGET"
            trigger = position.profit_target_pct
        elif (
            self.policy.enable_stop_loss_exit
            and position.stop_loss_pct is not None
            and return_pct <= -position.stop_loss_pct
        ):
            reason = "STOP_LOSS"
            trigger = -position.stop_loss_pct
        elif (
            self.policy.enable_trailing_stop_exit
            and position.trailing_stop_pct is not None
        ):
            anchor = (
                position.high_water_mark
                if position.quantity > 0
                else position.low_water_mark
            )
            if anchor:
                trailing_return = (
                    (position.market_price - anchor) / anchor * direction
                )
                if trailing_return <= -position.trailing_stop_pct:
                    reason = "TRAILING_STOP"
                    trigger = -position.trailing_stop_pct

        if reason is None:
            return PaperPositionDecision(
                valid=True,
                allowed=True,
                action="EXIT_EVALUATION",
                position_id=position.position_id,
                recommendation="HOLD",
                position=position,
            )

        signal = PaperExitSignal(
            position_id=position.position_id,
            action="SELL_TO_CLOSE" if position.quantity > 0 else "BUY_TO_CLOSE",
            reason=reason,
            quantity=abs(position.quantity),
            reference_price=position.market_price,
            trigger_value=trigger,
        )
        return PaperPositionDecision(
            valid=True,
            allowed=True,
            action="EXIT_EVALUATION",
            position_id=position.position_id,
            recommendation="EXIT",
            position=position,
            exit_signal=signal,
        )

    def close_with_fill(
        self,
        position: PaperPositionProfile,
        fill: PaperFillProfile,
    ) -> PaperPositionProfile:
        close_qty = min(abs(position.quantity), abs(fill.quantity))
        direction = 1.0 if position.quantity > 0 else -1.0
        realized = (
            (fill.fill_price - position.average_cost)
            * close_qty
            * position.multiplier
            * direction
            - fill.commission
        )
        remaining_signed = (
            position.quantity - close_qty
            if position.quantity > 0
            else position.quantity + close_qty
        )
        state = "CLOSED" if abs(remaining_signed) < 1e-12 else "PARTIALLY_CLOSED"
        now = datetime.now(timezone.utc).isoformat()
        return replace(
            position,
            quantity=round(remaining_signed, 6),
            realized_pnl=round(position.realized_pnl + realized, 6),
            unrealized_pnl=0.0 if state == "CLOSED" else position.unrealized_pnl,
            total_commissions=round(
                position.total_commissions + fill.commission,
                6,
            ),
            state=state,
            closed_at=now if state == "CLOSED" else None,
            updated_at=now,
        )

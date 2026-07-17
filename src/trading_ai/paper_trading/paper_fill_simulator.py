from __future__ import annotations

from datetime import datetime, timezone
import uuid

from .paper_commission_model import PaperCommissionModel
from .paper_execution_policy import PaperExecutionPolicy
from .paper_execution_profile import (
    PaperExecutionRequest,
    PaperFillProfile,
)
from .paper_latency_model import PaperLatencyModel
from .paper_slippage_model import PaperSlippageModel


class PaperFillSimulator:
    def __init__(
        self,
        policy: PaperExecutionPolicy | None = None,
    ) -> None:
        self.policy = policy or PaperExecutionPolicy()
        self.policy.validate()
        self.slippage = PaperSlippageModel(self.policy)
        self.commission = PaperCommissionModel(self.policy)
        self.latency = PaperLatencyModel(self.policy)

    @staticmethod
    def _reference_price(side: str, quote) -> float:
        return quote.ask if side.upper().startswith("BUY") else quote.bid

    @staticmethod
    def _marketable(
        *,
        side: str,
        order_type: str,
        limit_price: float | None,
        stop_price: float | None,
        quote,
    ) -> bool:
        side = side.upper()
        order_type = order_type.upper()
        if order_type == "MARKET":
            return True
        if order_type == "LIMIT":
            if limit_price is None:
                return False
            return (
                limit_price >= quote.ask
                if side.startswith("BUY")
                else limit_price <= quote.bid
            )
        if order_type == "STOP":
            if stop_price is None:
                return False
            return (
                quote.last >= stop_price
                if side.startswith("BUY")
                else quote.last <= stop_price
            )
        if order_type == "STOP_LIMIT":
            if stop_price is None or limit_price is None:
                return False
            triggered = (
                quote.last >= stop_price
                if side.startswith("BUY")
                else quote.last <= stop_price
            )
            limit_ok = (
                limit_price >= quote.ask
                if side.startswith("BUY")
                else limit_price <= quote.bid
            )
            return triggered and limit_ok
        return False

    def simulate(
        self,
        request: PaperExecutionRequest,
    ) -> tuple[PaperFillProfile, ...]:
        command = request.order_draft.command
        fills = []
        latency_ms = self.latency.resolve(
            request.metadata.get("latency_ms")
        )

        for leg in command.legs:
            quote = request.quotes[leg.symbol]
            if not self._marketable(
                side=leg.side,
                order_type=command.order_type,
                limit_price=command.limit_price,
                stop_price=command.stop_price,
                quote=quote,
            ):
                continue

            available_size = (
                quote.ask_size
                if leg.side.upper().startswith("BUY")
                else quote.bid_size
            )
            requested_quantity = abs(float(leg.quantity))
            if self.policy.allow_partial_fills:
                size_limit = (
                    available_size
                    if available_size > 0
                    else requested_quantity
                )
                quantity = min(
                    requested_quantity
                    * self.policy.maximum_fill_fraction_per_attempt,
                    size_limit,
                )
            else:
                quantity = requested_quantity

            if quantity <= 0:
                continue

            reference_price = self._reference_price(leg.side, quote)
            fill_price, slippage_amount, slippage_bps = self.slippage.apply(
                side=leg.side,
                reference_price=reference_price,
                quantity=quantity,
                available_size=available_size,
                slippage_bps=request.metadata.get("slippage_bps"),
            )
            commission = self.commission.calculate(
                asset_class=leg.asset_class,
                quantity=quantity,
            )
            fills.append(
                PaperFillProfile(
                    fill_id=f"paper-fill-{uuid.uuid4().hex}",
                    execution_key=request.execution_key,
                    aggregate_id=command.aggregate_id,
                    client_order_id=command.client_order_id,
                    leg_id=leg.leg_id,
                    symbol=leg.symbol,
                    side=leg.side,
                    quantity=round(quantity, 6),
                    fill_price=fill_price,
                    reference_price=round(reference_price, 6),
                    slippage_amount=slippage_amount,
                    slippage_bps=slippage_bps,
                    commission=commission,
                    latency_ms=latency_ms,
                    filled_at=datetime.now(timezone.utc).isoformat(),
                )
            )
        return tuple(fills)

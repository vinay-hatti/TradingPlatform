from __future__ import annotations

from .paper_execution_policy import PaperExecutionPolicy


class PaperSlippageModel:
    def __init__(self, policy: PaperExecutionPolicy | None = None) -> None:
        self.policy = policy or PaperExecutionPolicy()
        self.policy.validate()

    def apply(
        self,
        *,
        side: str,
        reference_price: float,
        quantity: float,
        available_size: float,
        slippage_bps: float | None = None,
    ) -> tuple[float, float, float]:
        bps = (
            self.policy.default_slippage_bps
            if slippage_bps is None
            else min(max(float(slippage_bps), 0.0), self.policy.maximum_slippage_bps)
        )
        size_pressure = 0.0
        if available_size > 0 and quantity > available_size:
            size_pressure = min(
                self.policy.maximum_slippage_bps - bps,
                bps * (quantity / available_size - 1.0),
            )
        effective_bps = min(
            self.policy.maximum_slippage_bps,
            bps + max(0.0, size_pressure),
        )
        direction = -1.0 if side.upper().startswith("SELL") else 1.0
        amount = reference_price * effective_bps / 10000.0
        fill_price = max(0.000001, reference_price + direction * amount)
        return round(fill_price, 6), round(amount, 6), round(effective_bps, 6)

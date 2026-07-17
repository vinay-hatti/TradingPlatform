from __future__ import annotations

from .paper_execution_policy import PaperExecutionPolicy


class PaperCommissionModel:
    def __init__(self, policy: PaperExecutionPolicy | None = None) -> None:
        self.policy = policy or PaperExecutionPolicy()
        self.policy.validate()

    def calculate(
        self,
        *,
        asset_class: str,
        quantity: float,
    ) -> float:
        if asset_class.upper() == "OPTION":
            commission = (
                abs(quantity) * self.policy.option_contract_commission
            )
        else:
            commission = (
                abs(quantity) * self.policy.equity_per_share_commission
            )
        return round(
            max(self.policy.minimum_commission_per_order, commission),
            6,
        )

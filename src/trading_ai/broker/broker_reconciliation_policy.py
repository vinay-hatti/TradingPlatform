from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrokerReconciliationPolicy:
    allowed_order_statuses: tuple[str, ...] = (
        "ACCEPTED",
        "PENDING",
        "WORKING",
        "PARTIALLY_FILLED",
        "FILLED",
        "CANCELED",
        "REPLACED",
        "REJECTED",
        "EXPIRED",
    )
    maximum_quantity_difference: float = 0.000001
    maximum_average_price_difference_pct: float = 0.01
    maximum_position_quantity_difference: float = 0.000001
    maximum_cost_basis_difference_pct: float = 0.01
    maximum_event_age_seconds: float = 300.0
    require_monotonic_fill_quantity: bool = True
    reject_overfills: bool = True
    reject_negative_fills: bool = True
    require_order_match: bool = True
    require_position_match: bool = True
    fail_closed: bool = True
    minimum_reconciliation_score: float = 85.0

    def validate(self) -> None:
        if not self.allowed_order_statuses:
            raise ValueError("allowed_order_statuses cannot be empty")
        if self.maximum_quantity_difference < 0:
            raise ValueError("maximum_quantity_difference cannot be negative")
        if self.maximum_average_price_difference_pct < 0:
            raise ValueError(
                "maximum_average_price_difference_pct cannot be negative"
            )
        if self.maximum_position_quantity_difference < 0:
            raise ValueError(
                "maximum_position_quantity_difference cannot be negative"
            )
        if self.maximum_cost_basis_difference_pct < 0:
            raise ValueError(
                "maximum_cost_basis_difference_pct cannot be negative"
            )
        if self.maximum_event_age_seconds < 0:
            raise ValueError("maximum_event_age_seconds cannot be negative")
        if not 0.0 <= self.minimum_reconciliation_score <= 100.0:
            raise ValueError(
                "minimum_reconciliation_score must be between 0 and 100"
            )

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrokerExecutionPolicy:
    require_broker_readiness: bool = True
    require_order_validation: bool = True
    require_idempotency_key: bool = True
    allow_idempotent_replay: bool = True
    reject_payload_mismatch_on_replay: bool = True
    allow_cancel_terminal_orders: bool = False
    allow_replace_terminal_orders: bool = False
    allow_replace_filled_orders: bool = False
    maximum_replace_count: int = 20
    terminal_statuses: tuple[str, ...] = (
        "FILLED",
        "CANCELED",
        "REJECTED",
        "EXPIRED",
    )
    cancellable_statuses: tuple[str, ...] = (
        "ACCEPTED",
        "PENDING",
        "WORKING",
        "PARTIALLY_FILLED",
    )
    replaceable_statuses: tuple[str, ...] = (
        "ACCEPTED",
        "PENDING",
        "WORKING",
        "PARTIALLY_FILLED",
    )
    minimum_execution_score: float = 85.0
    fail_closed: bool = True

    def validate(self) -> None:
        if self.maximum_replace_count < 0:
            raise ValueError("maximum_replace_count cannot be negative")
        if not 0.0 <= self.minimum_execution_score <= 100.0:
            raise ValueError(
                "minimum_execution_score must be between 0 and 100"
            )
        if not self.terminal_statuses:
            raise ValueError("terminal_statuses cannot be empty")

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .order_profile import CanonicalOrderAggregate, CanonicalOrderCommand
from .order_service import CanonicalOrderService


class OrderCommandHandler:
    """Dispatch canonical commands to aggregate creation or state transitions."""

    TRANSITION_ACTIONS = {
        "VALIDATE",
        "ROUTE",
        "SUBMIT",
        "ACKNOWLEDGE",
        "WORK",
        "PARTIAL_FILL",
        "FILL",
        "CANCEL_REQUEST",
        "CANCEL",
        "REPLACE_REQUEST",
        "REPLACE",
        "REJECT",
        "EXPIRE",
    }

    def __init__(self, service: CanonicalOrderService | None = None) -> None:
        self.service = service or CanonicalOrderService()

    def handle(
        self,
        command: CanonicalOrderCommand,
        *,
        aggregate: CanonicalOrderAggregate | None = None,
        event_id: str | None = None,
        broker_order_id: str | None = None,
        filled_quantity: float | None = None,
        average_fill_price: float | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        command_type = command.command_type.strip().upper()
        if command_type == "CREATE":
            return self.service.create(command)

        if command_type not in self.TRANSITION_ACTIONS:
            raise ValueError(f"Unsupported order command: {command_type}")
        if aggregate is None:
            raise ValueError("aggregate is required for transition commands")
        if not event_id:
            raise ValueError("event_id is required for transition commands")

        return self.service.transition(
            aggregate,
            command_type,
            event_id=event_id,
            broker_order_id=broker_order_id,
            filled_quantity=filled_quantity,
            average_fill_price=average_fill_price,
            reason=command.reason,
            correlation_id=command.correlation_id,
            causation_id=command.causation_id,
            metadata=metadata or command.metadata,
        )

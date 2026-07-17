from dataclasses import dataclass, field
from typing import Any

ORDER_COMMAND_TYPES = ("CREATE","VALIDATE","ROUTE","SUBMIT","ACKNOWLEDGE","WORK","PARTIAL_FILL","FILL","CANCEL_REQUEST","CANCEL","REPLACE_REQUEST","REPLACE","REJECT","EXPIRE")
ORDER_EVENT_TYPES = ("ORDER_CREATED","ORDER_VALIDATED","ORDER_ROUTED","ORDER_SUBMITTED","ORDER_ACKNOWLEDGED","ORDER_WORKING","ORDER_PARTIALLY_FILLED","ORDER_FILLED","ORDER_CANCEL_REQUESTED","ORDER_CANCELED","ORDER_REPLACE_REQUESTED","ORDER_REPLACED","ORDER_REJECTED","ORDER_EXPIRED")

@dataclass(frozen=True)
class OrderLifecycleEventEnvelope:
    event_type: str
    aggregate_id: str
    payload: dict[str, Any]
    event_id: str
    occurred_at: str
    aggregate_version: int
    correlation_id: str | None = None
    causation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

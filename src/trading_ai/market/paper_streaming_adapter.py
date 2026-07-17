from __future__ import annotations

import uuid
from collections import deque
from typing import Any

from .realtime_provider_adapter import RealTimeMarketDataProviderAdapter
from .realtime_provider_profile import (
    ProviderCapabilitiesProfile,
    SubscriptionRequest,
)
from .realtime_pipeline_profile import PaperStreamEventProfile


class PaperStreamingAdapter(RealTimeMarketDataProviderAdapter):
    """Deterministic in-process adapter for paper and regression workflows."""

    def __init__(self, provider_name: str = "paper") -> None:
        self._provider_name = provider_name.strip().lower()
        self._connected = False
        self._connection_id: str | None = None
        self._subscriptions: dict[str, SubscriptionRequest] = {}
        self._events: deque[PaperStreamEventProfile] = deque()
        self._sequence = 0

    @property
    def provider_name(self) -> str:
        return self._provider_name

    def capabilities(self) -> ProviderCapabilitiesProfile:
        return ProviderCapabilitiesProfile(
            provider=self.provider_name,
            supports_quotes=True,
            supports_trades=True,
            supports_options=True,
            supports_equities=True,
            supports_heartbeat=True,
            supports_sequence_numbers=True,
        )

    def connect(self) -> str:
        self._connected = True
        self._connection_id = f"{self.provider_name}-{uuid.uuid4().hex[:12]}"
        self.emit_lifecycle(
            "CONNECTED",
            {"connection_id": self._connection_id},
        )
        return self._connection_id

    def disconnect(self) -> None:
        self._connected = False
        self.emit_lifecycle(
            "DISCONNECTED",
            {"connection_id": self._connection_id},
        )

    def subscribe(self, request: SubscriptionRequest) -> None:
        if not self._connected:
            raise RuntimeError("paper adapter is not connected")
        self._subscriptions[request.subscription_id] = request
        self.emit_lifecycle(
            "SUBSCRIBED",
            {"subscription_id": request.subscription_id},
        )

    def unsubscribe(self, subscription_id: str) -> None:
        self._subscriptions.pop(subscription_id, None)
        self.emit_lifecycle(
            "UNSUBSCRIBED",
            {"subscription_id": subscription_id},
        )

    def is_connected(self) -> bool:
        return self._connected

    def queue_quote(self, symbol: str, **payload: Any) -> PaperStreamEventProfile:
        return self._queue("QUOTE", symbol, payload)

    def queue_trade(self, symbol: str, **payload: Any) -> PaperStreamEventProfile:
        return self._queue("TRADE", symbol, payload)

    def _queue(
        self,
        event_type: str,
        symbol: str,
        payload: dict[str, Any],
    ) -> PaperStreamEventProfile:
        self._sequence += 1
        event = PaperStreamEventProfile(
            event_type=event_type,
            symbol=str(symbol).strip().upper(),
            payload=dict(payload),
            sequence_number=self._sequence,
            provider=self.provider_name,
        )
        self._events.append(event)
        return event

    def pending_count(self) -> int:
        return len(self._events)

    def emit_next(self) -> PaperStreamEventProfile | None:
        if not self._connected:
            raise RuntimeError("paper adapter is not connected")
        if not self._events:
            return None
        event = self._events.popleft()
        self.emit_event(event)
        return event

    def emit_all(self) -> tuple[PaperStreamEventProfile, ...]:
        emitted: list[PaperStreamEventProfile] = []
        while self._events:
            event = self.emit_next()
            if event is not None:
                emitted.append(event)
        return tuple(emitted)

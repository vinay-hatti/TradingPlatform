from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Callable

from .realtime_pipeline_profile import (
    DispatchedMarketEvent,
    PipelineSubscriberProfile,
)


MarketEventHandler = Callable[[DispatchedMarketEvent], None]


class RealTimeMarketEventDispatcher:
    def __init__(self) -> None:
        self._handlers: dict[str, MarketEventHandler] = {}
        self._profiles: dict[str, PipelineSubscriberProfile] = {}

    @staticmethod
    def _normalize_values(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        return tuple(sorted({str(value).strip().upper() for value in values if str(value).strip()}))

    def subscribe(
        self,
        subscriber_id: str,
        handler: MarketEventHandler,
        *,
        event_types: tuple[str, ...] = ("QUOTE", "TRADE"),
        symbols: tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> PipelineSubscriberProfile:
        if subscriber_id in self._handlers:
            raise ValueError(f"Subscriber already exists: {subscriber_id}")
        profile = PipelineSubscriberProfile(
            subscriber_id=subscriber_id,
            event_types=self._normalize_values(event_types),
            symbols=self._normalize_values(symbols),
            metadata=metadata or {},
        )
        self._handlers[subscriber_id] = handler
        self._profiles[subscriber_id] = profile
        return profile

    def unsubscribe(self, subscriber_id: str) -> PipelineSubscriberProfile | None:
        self._handlers.pop(subscriber_id, None)
        return self._profiles.pop(subscriber_id, None)

    def profiles(self) -> tuple[PipelineSubscriberProfile, ...]:
        return tuple(sorted(self._profiles.values(), key=lambda item: item.subscriber_id))

    def dispatch(self, event: DispatchedMarketEvent) -> tuple[str, ...]:
        errors: list[str] = []
        for subscriber_id, handler in tuple(self._handlers.items()):
            profile = self._profiles[subscriber_id]
            if not profile.active:
                continue
            if profile.event_types and event.event_type.upper() not in profile.event_types:
                continue
            if profile.symbols and event.symbol.upper() not in profile.symbols:
                continue
            try:
                handler(event)
                self._profiles[subscriber_id] = replace(
                    profile,
                    delivered_count=profile.delivered_count + 1,
                    last_delivery_at=datetime.now(timezone.utc).isoformat(),
                )
            except Exception as exc:
                self._profiles[subscriber_id] = replace(
                    profile,
                    error_count=profile.error_count + 1,
                )
                errors.append(f"{subscriber_id}:{exc}")
        return tuple(errors)

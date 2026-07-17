from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from .realtime_provider_profile import (
    ProviderCapabilitiesProfile,
    SubscriptionRequest,
)


MarketEventCallback = Callable[[Any], None]
LifecycleCallback = Callable[[str, dict[str, Any]], None]


class RealTimeMarketDataProviderAdapter(ABC):
    """Provider-neutral streaming adapter contract."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def capabilities(self) -> ProviderCapabilitiesProfile:
        raise NotImplementedError

    @abstractmethod
    def connect(self) -> str:
        """Connect and return a provider connection id."""
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def subscribe(self, request: SubscriptionRequest) -> None:
        raise NotImplementedError

    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_connected(self) -> bool:
        raise NotImplementedError

    def set_event_callback(self, callback: MarketEventCallback | None) -> None:
        self._event_callback = callback

    def set_lifecycle_callback(self, callback: LifecycleCallback | None) -> None:
        self._lifecycle_callback = callback

    def emit_event(self, event: Any) -> None:
        callback = getattr(self, "_event_callback", None)
        if callback:
            callback(event)

    def emit_lifecycle(self, event: str, metadata: dict[str, Any] | None = None) -> None:
        callback = getattr(self, "_lifecycle_callback", None)
        if callback:
            callback(event, metadata or {})

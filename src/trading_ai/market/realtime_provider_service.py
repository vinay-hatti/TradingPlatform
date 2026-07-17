from __future__ import annotations

from pathlib import Path
from typing import Any

from .realtime_connection_lifecycle import ProviderConnectionLifecycle
from .realtime_provider_adapter import RealTimeMarketDataProviderAdapter
from .realtime_provider_policy import RealTimeProviderPolicy
from .realtime_provider_profile import ProviderLifecycleResult, SubscriptionRequest
from .realtime_subscription_registry import RealTimeSubscriptionRegistry


class RealTimeProviderService:
    def __init__(
        self,
        adapter: RealTimeMarketDataProviderAdapter,
        *,
        registry_path: str | Path = "config/realtime_subscriptions.json",
        policy: RealTimeProviderPolicy | None = None,
    ) -> None:
        self.adapter = adapter
        self.policy = policy or RealTimeProviderPolicy()
        self.lifecycle = ProviderConnectionLifecycle(adapter.provider_name, self.policy)
        self.registry = RealTimeSubscriptionRegistry(registry_path, self.policy)

    def connect(self) -> ProviderLifecycleResult:
        self.lifecycle.connecting()
        try:
            connection_id = self.adapter.connect()
            profile = self.lifecycle.connected(connection_id)
            return ProviderLifecycleResult(
                valid=True,
                allowed=True,
                connection=profile,
                subscriptions=self.registry.all(self.adapter.provider_name),
            )
        except Exception as exc:
            profile = self.lifecycle.disconnected("CONNECTION_FAILED")
            return ProviderLifecycleResult(
                valid=False,
                allowed=False,
                connection=profile,
                subscriptions=self.registry.all(self.adapter.provider_name),
                rejection_reasons=("CONNECTION_FAILED",),
                metadata={"error": str(exc)},
            )

    def disconnect(self) -> ProviderLifecycleResult:
        try:
            self.adapter.disconnect()
            profile = self.lifecycle.stopped()
            return ProviderLifecycleResult(
                valid=True,
                allowed=False,
                connection=profile,
                subscriptions=self.registry.all(self.adapter.provider_name),
            )
        except Exception as exc:
            profile = self.lifecycle.disconnected("DISCONNECT_FAILED")
            return ProviderLifecycleResult(
                valid=False,
                allowed=False,
                connection=profile,
                rejection_reasons=("DISCONNECT_FAILED",),
                metadata={"error": str(exc)},
            )

    def subscribe(self, request: SubscriptionRequest, persist: bool = True):
        profile = self.registry.register(request)
        if profile.rejection_reasons:
            return profile
        if not self.adapter.is_connected():
            return self.registry.update_status(profile.subscription_id, "PENDING")
        try:
            self.adapter.subscribe(request)
            updated = self.registry.update_status(profile.subscription_id, "ACTIVE")
        except Exception:
            updated = self.registry.update_status(profile.subscription_id, "FAILED")
        if persist:
            self.registry.save()
        return updated

    def unsubscribe(self, subscription_id: str, persist: bool = True):
        current = self.registry.get(subscription_id)
        if current is None:
            return None
        try:
            self.adapter.unsubscribe(subscription_id)
            removed = self.registry.remove(subscription_id)
        except Exception:
            removed = self.registry.update_status(subscription_id, "FAILED")
        if persist:
            self.registry.save()
        return removed

    def reconnect(self) -> ProviderLifecycleResult:
        profile = self.lifecycle.reconnecting()
        if profile.state == "FAILED":
            return ProviderLifecycleResult(
                valid=False,
                allowed=False,
                connection=profile,
                subscriptions=self.registry.all(self.adapter.provider_name),
                rejection_reasons=profile.rejection_reasons,
            )
        return self.connect()

    def heartbeat(self) -> ProviderLifecycleResult:
        profile = self.lifecycle.heartbeat()
        return ProviderLifecycleResult(
            valid=True,
            allowed=profile.connected,
            connection=profile,
            subscriptions=self.registry.all(self.adapter.provider_name),
        )

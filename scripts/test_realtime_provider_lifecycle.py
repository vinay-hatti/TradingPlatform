from __future__ import annotations

import tempfile
from pathlib import Path

from trading_ai.market.realtime_provider_adapter import (
    RealTimeMarketDataProviderAdapter,
)
from trading_ai.market.realtime_provider_policy import RealTimeProviderPolicy
from trading_ai.market.realtime_provider_profile import (
    ProviderCapabilitiesProfile,
    SubscriptionRequest,
)
from trading_ai.market.realtime_provider_serialization import dumps
from trading_ai.market.realtime_provider_service import RealTimeProviderService
from trading_ai.market.realtime_subscription_registry import (
    RealTimeSubscriptionRegistry,
)


class FakeProviderAdapter(RealTimeMarketDataProviderAdapter):
    def __init__(self) -> None:
        self.connected = False
        self.subscriptions: set[str] = set()

    @property
    def provider_name(self) -> str:
        return "fake"

    def capabilities(self) -> ProviderCapabilitiesProfile:
        return ProviderCapabilitiesProfile(
            provider="fake",
            supports_quotes=True,
            supports_trades=True,
            supports_sequence_numbers=True,
        )

    def connect(self) -> str:
        self.connected = True
        return "fake-connection-1"

    def disconnect(self) -> None:
        self.connected = False

    def subscribe(self, request: SubscriptionRequest) -> None:
        if not self.connected:
            raise RuntimeError("not connected")
        self.subscriptions.add(request.subscription_id)

    def unsubscribe(self, subscription_id: str) -> None:
        self.subscriptions.discard(subscription_id)

    def is_connected(self) -> bool:
        return self.connected


def main() -> None:
    policy = RealTimeProviderPolicy(
        maximum_symbols_per_subscription=3,
        maximum_reconnect_attempts=2,
        reconnect_initial_delay_seconds=1.0,
        reconnect_max_delay_seconds=4.0,
    )

    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "config/realtime_subscriptions.json"
        adapter = FakeProviderAdapter()
        service = RealTimeProviderService(
            adapter,
            registry_path=path,
            policy=policy,
        )

        connected = service.connect()
        assert connected.valid
        assert connected.allowed
        assert connected.connection.state == "CONNECTED"
        assert connected.connection.connection_id == "fake-connection-1"

        request = SubscriptionRequest(
            subscription_id="core",
            provider="fake",
            symbols=("aapl", "MSFT", "aapl"),
            channels=("quotes", "trades"),
        )
        subscription = service.subscribe(request)
        assert subscription.status == "ACTIVE"
        assert subscription.symbols == ("AAPL", "MSFT")
        assert "core" in adapter.subscriptions

        duplicate = service.subscribe(request)
        assert duplicate.status == "REJECTED"
        assert "DUPLICATE_SUBSCRIPTION" in duplicate.rejection_reasons

        too_many = service.subscribe(
            SubscriptionRequest(
                subscription_id="too-many",
                provider="fake",
                symbols=("AAPL", "MSFT", "AMZN", "GOOGL"),
            )
        )
        assert too_many.status == "REJECTED"
        assert "SYMBOL_LIMIT_EXCEEDED" in too_many.rejection_reasons

        heartbeat = service.heartbeat()
        assert heartbeat.connection.last_heartbeat_at is not None

        removed = service.unsubscribe("core")
        assert removed is not None
        assert service.registry.get("core") is None

        disconnected = service.disconnect()
        assert disconnected.connection.state == "STOPPED"
        assert not adapter.is_connected()

        registry = RealTimeSubscriptionRegistry(path, policy)
        assert registry.all() == ()

        serialized = dumps(connected)
        assert '"state": "CONNECTED"' in serialized
        assert '"provider": "fake"' in serialized

    print(
        "All provider-adapter, subscription-registry and "
        "connection-lifecycle assertions passed."
    )


if __name__ == "__main__":
    main()

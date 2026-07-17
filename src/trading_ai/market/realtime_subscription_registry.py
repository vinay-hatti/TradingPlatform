from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

from .realtime_provider_policy import RealTimeProviderPolicy
from .realtime_provider_profile import SubscriptionProfile, SubscriptionRequest


class RealTimeSubscriptionRegistry:
    def __init__(
        self,
        path: str | Path = "config/realtime_subscriptions.json",
        policy: RealTimeProviderPolicy | None = None,
    ) -> None:
        self.path = Path(path)
        self.policy = policy or RealTimeProviderPolicy()
        self.policy.validate()
        self._subscriptions: dict[str, SubscriptionProfile] = {}
        if self.path.exists():
            self.load()

    @staticmethod
    def _normalize_symbols(symbols: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        return tuple(sorted({str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()}))

    def register(self, request: SubscriptionRequest) -> SubscriptionProfile:
        symbols = self._normalize_symbols(request.symbols)
        reasons: list[str] = []
        if not symbols:
            reasons.append("NO_SYMBOLS")
        if len(symbols) > self.policy.maximum_symbols_per_subscription:
            reasons.append("SYMBOL_LIMIT_EXCEEDED")
        if request.subscription_id in self._subscriptions and not self.policy.allow_duplicate_subscriptions:
            reasons.append("DUPLICATE_SUBSCRIPTION")
        status = "REJECTED" if reasons else "REGISTERED"
        profile = SubscriptionProfile(
            subscription_id=request.subscription_id,
            provider=request.provider.strip().lower(),
            symbols=symbols,
            channels=tuple(channel.strip().upper() for channel in request.channels),
            asset_class=request.asset_class.strip().upper(),
            status=status,
            rejection_reasons=tuple(reasons),
            metadata=dict(request.metadata),
        )
        if not reasons:
            self._subscriptions[profile.subscription_id] = profile
        return profile

    def update_status(self, subscription_id: str, status: str) -> SubscriptionProfile:
        current = self._subscriptions[subscription_id]
        updated = replace(
            current,
            status=status,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._subscriptions[subscription_id] = updated
        return updated

    def remove(self, subscription_id: str) -> SubscriptionProfile | None:
        return self._subscriptions.pop(subscription_id, None)

    def get(self, subscription_id: str) -> SubscriptionProfile | None:
        return self._subscriptions.get(subscription_id)

    def all(self, provider: str | None = None) -> tuple[SubscriptionProfile, ...]:
        values = self._subscriptions.values()
        if provider is not None:
            normalized = provider.strip().lower()
            values = [item for item in values if item.provider == normalized]
        return tuple(sorted(values, key=lambda item: item.subscription_id))

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"subscriptions": [asdict(item) for item in self._subscriptions.values()]}
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return self.path

    def load(self) -> None:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self._subscriptions = {}
        for raw in payload.get("subscriptions", []):
            raw["symbols"] = tuple(raw.get("symbols", ()))
            raw["channels"] = tuple(raw.get("channels", ()))
            raw["warnings"] = tuple(raw.get("warnings", ()))
            raw["rejection_reasons"] = tuple(raw.get("rejection_reasons", ()))
            profile = SubscriptionProfile(**raw)
            self._subscriptions[profile.subscription_id] = profile

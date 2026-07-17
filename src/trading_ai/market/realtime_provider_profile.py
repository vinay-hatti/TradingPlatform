from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ProviderCapabilitiesProfile:
    provider: str
    supports_quotes: bool = True
    supports_trades: bool = True
    supports_options: bool = False
    supports_equities: bool = True
    supports_heartbeat: bool = True
    supports_sequence_numbers: bool = False
    maximum_symbols_per_subscription: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SubscriptionRequest:
    subscription_id: str
    provider: str
    symbols: tuple[str, ...]
    channels: tuple[str, ...] = ("QUOTES", "TRADES")
    asset_class: str = "EQUITY"
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SubscriptionProfile:
    subscription_id: str
    provider: str
    symbols: tuple[str, ...]
    channels: tuple[str, ...]
    asset_class: str
    status: str
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderConnectionProfile:
    provider: str
    state: str
    connected: bool
    connection_id: str | None = None
    connected_at: str | None = None
    disconnected_at: str | None = None
    last_heartbeat_at: str | None = None
    reconnect_attempts: int = 0
    next_reconnect_delay_seconds: float = 0.0
    score: float = 0.0
    grade: str = "F"
    severity: str = "CRITICAL"
    allowed: bool = False
    recommendation: str = "CONNECT"
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderLifecycleResult:
    valid: bool
    allowed: bool
    connection: ProviderConnectionProfile
    subscriptions: tuple[SubscriptionProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

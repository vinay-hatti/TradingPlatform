from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class BrokerCapabilitiesProfile:
    broker: str
    supports_equities: bool = True
    supports_options: bool = False
    supports_multi_leg_options: bool = False
    supports_fractional_shares: bool = False
    supports_order_replace: bool = True
    supports_streaming_orders: bool = False
    supports_streaming_positions: bool = False
    supports_paper_trading: bool = True
    supports_live_trading: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerAuthenticationRequest:
    environment: str
    account_id: str | None = None
    client_id_secret_name: str | None = None
    client_secret_secret_name: str | None = None
    access_token_secret_name: str | None = None
    refresh_token_secret_name: str | None = None
    redirect_uri: str | None = None
    live_trading_requested: bool = False
    manual_live_approval: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerAuthenticationProfile:
    broker: str
    environment: str
    authenticated: bool
    session_id: str | None = None
    account_id: str | None = None
    authenticated_at: str | None = None
    expires_at: str | None = None
    token_age_seconds: float | None = None
    seconds_until_expiry: float | None = None
    live_trading_enabled: bool = False
    score: float = 0.0
    grade: str = "F"
    severity: str = "CRITICAL"
    allowed: bool = False
    recommendation: str = "AUTHENTICATE"
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerAccountProfile:
    broker: str
    account_id: str
    account_type: str
    currency: str
    status: str
    net_liquidation: float
    cash_balance: float
    buying_power: float
    option_buying_power: float
    maintenance_requirement: float = 0.0
    excess_liquidity: float = 0.0
    day_trade_buying_power: float = 0.0
    accrued_interest: float = 0.0
    trading_permission: bool = True
    options_permission: bool = False
    market_data_permission: bool = False
    paper_account: bool = True
    as_of: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerReadinessCheckProfile:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerReadinessProfile:
    valid: bool
    allowed: bool
    broker: str
    environment: str
    score: float
    grade: str
    severity: str
    recommendation: str
    authentication: BrokerAuthenticationProfile | None = None
    account: BrokerAccountProfile | None = None
    capabilities: BrokerCapabilitiesProfile | None = None
    checks: tuple[BrokerReadinessCheckProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from .broker_adapter import BrokerAdapter
from .broker_profile import (
    BrokerAccountProfile,
    BrokerAuthenticationProfile,
    BrokerAuthenticationRequest,
    BrokerCapabilitiesProfile,
)


class FakeBrokerAdapter(BrokerAdapter):
    """Deterministic adapter for paper workflows and regression tests."""

    def __init__(
        self,
        *,
        broker_name: str = "fake",
        account_id: str = "PAPER-001",
        net_liquidation: float = 100000.0,
        buying_power: float = 200000.0,
        option_buying_power: float = 100000.0,
    ) -> None:
        self._broker_name = broker_name
        self._account = BrokerAccountProfile(
            broker=broker_name,
            account_id=account_id,
            account_type="MARGIN",
            currency="USD",
            status="ACTIVE",
            net_liquidation=net_liquidation,
            cash_balance=50000.0,
            buying_power=buying_power,
            option_buying_power=option_buying_power,
            maintenance_requirement=10000.0,
            excess_liquidity=90000.0,
            day_trade_buying_power=400000.0,
            trading_permission=True,
            options_permission=True,
            market_data_permission=True,
            paper_account=True,
        )
        self._auth: BrokerAuthenticationProfile | None = None

    @property
    def broker_name(self) -> str:
        return self._broker_name

    def capabilities(self) -> BrokerCapabilitiesProfile:
        return BrokerCapabilitiesProfile(
            broker=self.broker_name,
            supports_equities=True,
            supports_options=True,
            supports_multi_leg_options=True,
            supports_order_replace=True,
            supports_streaming_orders=True,
            supports_streaming_positions=True,
            supports_paper_trading=True,
            supports_live_trading=False,
        )

    def authenticate(
        self,
        request: BrokerAuthenticationRequest,
    ) -> BrokerAuthenticationProfile:
        now = datetime.now(timezone.utc)
        live_enabled = bool(
            request.live_trading_requested
            and request.manual_live_approval
        )
        self._auth = BrokerAuthenticationProfile(
            broker=self.broker_name,
            environment=request.environment,
            authenticated=True,
            session_id=f"session-{uuid.uuid4().hex[:12]}",
            account_id=request.account_id or self._account.account_id,
            authenticated_at=now.isoformat(),
            expires_at=(now + timedelta(hours=1)).isoformat(),
            live_trading_enabled=live_enabled,
            metadata={"adapter": "fake"},
        )
        return self._auth

    def refresh_authentication(self) -> BrokerAuthenticationProfile:
        if self._auth is None:
            raise RuntimeError("broker is not authenticated")
        now = datetime.now(timezone.utc)
        self._auth = BrokerAuthenticationProfile(
            broker=self._auth.broker,
            environment=self._auth.environment,
            authenticated=True,
            session_id=self._auth.session_id,
            account_id=self._auth.account_id,
            authenticated_at=now.isoformat(),
            expires_at=(now + timedelta(hours=1)).isoformat(),
            live_trading_enabled=self._auth.live_trading_enabled,
            metadata=dict(self._auth.metadata),
        )
        return self._auth

    def logout(self) -> None:
        self._auth = None

    def is_authenticated(self) -> bool:
        return self._auth is not None and self._auth.authenticated

    def authentication_profile(self) -> BrokerAuthenticationProfile | None:
        return self._auth

    def get_account_profile(self) -> BrokerAccountProfile:
        if not self.is_authenticated():
            raise RuntimeError("broker is not authenticated")
        return self._account

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from trading_ai.broker.broker_authentication_engine import (
    BrokerAuthenticationEngine,
)
from trading_ai.broker.broker_policy import BrokerPolicy
from trading_ai.broker.broker_profile import (
    BrokerAuthenticationProfile,
    BrokerAuthenticationRequest,
)
from trading_ai.broker.broker_serialization import dumps
from trading_ai.broker.broker_service import BrokerService
from trading_ai.broker.fake_broker_adapter import FakeBrokerAdapter


def main() -> None:
    policy = BrokerPolicy(
        require_options_permission=True,
        require_market_data_permission=True,
    )
    adapter = FakeBrokerAdapter()
    service = BrokerService(adapter, policy=policy)

    readiness = service.authenticate(
        BrokerAuthenticationRequest(
            environment="paper",
            account_id="PAPER-001",
            live_trading_requested=False,
        )
    )
    assert readiness.valid
    assert readiness.allowed
    assert readiness.recommendation == "READY"
    assert readiness.authentication is not None
    assert readiness.authentication.allowed
    assert readiness.account is not None
    assert readiness.account.buying_power == 200000.0
    assert readiness.account.options_permission
    assert readiness.capabilities is not None
    assert readiness.capabilities.supports_options

    refreshed = service.refresh()
    assert refreshed.allowed
    assert refreshed.authentication is not None
    assert refreshed.authentication.recommendation == "USE_SESSION"

    current = service.readiness()
    assert current.allowed

    serialized = dumps(readiness)
    assert '"broker": "fake"' in serialized
    assert '"recommendation": "READY"' in serialized
    assert "secure-password" not in serialized

    now = datetime.now(timezone.utc)
    expired = BrokerAuthenticationProfile(
        broker="fake",
        environment="paper",
        authenticated=True,
        session_id="expired-session",
        account_id="PAPER-001",
        authenticated_at=(now - timedelta(hours=2)).isoformat(),
        expires_at=(now - timedelta(seconds=1)).isoformat(),
    )
    evaluated = BrokerAuthenticationEngine(policy).evaluate_authentication(
        expired,
        now=now,
    )
    assert not evaluated.allowed
    assert "BROKER_TOKEN_TOO_OLD" in evaluated.rejection_reasons
    assert "BROKER_TOKEN_EXPIRED" in evaluated.rejection_reasons

    live_outside_production = BrokerAuthenticationProfile(
        broker="fake",
        environment="paper",
        authenticated=True,
        session_id="live-session",
        account_id="PAPER-001",
        authenticated_at=now.isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
        live_trading_enabled=True,
    )
    live_evaluated = BrokerAuthenticationEngine(policy).evaluate_authentication(
        live_outside_production,
        now=now,
    )
    assert not live_evaluated.allowed
    assert (
        "LIVE_BROKER_OUTSIDE_PRODUCTION"
        in live_evaluated.rejection_reasons
    )

    service.logout()
    assert not adapter.is_authenticated()
    blocked = service.readiness()
    assert not blocked.allowed
    assert "AUTHENTICATION" in blocked.rejection_reasons

    print(
        "All broker adapter, account profile and authentication-foundation "
        "assertions passed."
    )


if __name__ == "__main__":
    main()

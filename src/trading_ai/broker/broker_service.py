from __future__ import annotations

from .broker_adapter import BrokerAdapter
from .broker_authentication_engine import BrokerAuthenticationEngine
from .broker_error import BrokerAdapterError, normalize_broker_error
from .broker_policy import BrokerPolicy
from .broker_profile import (
    BrokerAuthenticationRequest,
    BrokerReadinessProfile,
)


class BrokerService:
    """Coordinate broker authentication, account retrieval, and readiness."""

    def __init__(
        self,
        adapter: BrokerAdapter,
        *,
        policy: BrokerPolicy | None = None,
    ) -> None:
        self.adapter = adapter
        self.policy = policy or BrokerPolicy()
        self.engine = BrokerAuthenticationEngine(self.policy)

    def authenticate(
        self,
        request: BrokerAuthenticationRequest,
    ) -> BrokerReadinessProfile:
        try:
            raw_auth = self.adapter.authenticate(request)
            auth = self.engine.evaluate_authentication(raw_auth)
            account = self.adapter.get_account_profile()
            capabilities = self.adapter.capabilities()
            return self.engine.evaluate_readiness(
                auth,
                account,
                capabilities,
            )
        except BrokerAdapterError:
            raise
        except Exception as exc:
            raise BrokerAdapterError(
                normalize_broker_error(
                    self.adapter.broker_name,
                    exc,
                    category="AUTHENTICATION",
                    retryable=True,
                )
            ) from exc

    def refresh(self) -> BrokerReadinessProfile:
        try:
            raw_auth = self.adapter.refresh_authentication()
            auth = self.engine.evaluate_authentication(raw_auth)
            return self.engine.evaluate_readiness(
                auth,
                self.adapter.get_account_profile(),
                self.adapter.capabilities(),
            )
        except BrokerAdapterError:
            raise
        except Exception as exc:
            raise BrokerAdapterError(
                normalize_broker_error(
                    self.adapter.broker_name,
                    exc,
                    category="TOKEN_REFRESH",
                    retryable=True,
                )
            ) from exc

    def readiness(self) -> BrokerReadinessProfile:
        auth = self.adapter.authentication_profile()
        evaluated = (
            self.engine.evaluate_authentication(auth)
            if auth is not None
            else None
        )
        account = None
        if self.adapter.is_authenticated():
            account = self.adapter.get_account_profile()
        return self.engine.evaluate_readiness(
            evaluated,
            account,
            self.adapter.capabilities(),
        )

    def logout(self) -> None:
        self.adapter.logout()

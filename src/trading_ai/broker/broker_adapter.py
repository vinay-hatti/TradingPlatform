from __future__ import annotations

from abc import ABC, abstractmethod

from .broker_profile import (
    BrokerAccountProfile,
    BrokerAuthenticationProfile,
    BrokerAuthenticationRequest,
    BrokerCapabilitiesProfile,
)


class BrokerAdapter(ABC):
    """Provider-neutral broker contract for account and authentication flows."""

    @property
    @abstractmethod
    def broker_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def capabilities(self) -> BrokerCapabilitiesProfile:
        raise NotImplementedError

    @abstractmethod
    def authenticate(
        self,
        request: BrokerAuthenticationRequest,
    ) -> BrokerAuthenticationProfile:
        raise NotImplementedError

    @abstractmethod
    def refresh_authentication(self) -> BrokerAuthenticationProfile:
        raise NotImplementedError

    @abstractmethod
    def logout(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_authenticated(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def authentication_profile(self) -> BrokerAuthenticationProfile | None:
        raise NotImplementedError

    @abstractmethod
    def get_account_profile(self) -> BrokerAccountProfile:
        raise NotImplementedError

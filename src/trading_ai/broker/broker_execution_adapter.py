from __future__ import annotations

from abc import ABC, abstractmethod

from .broker_execution_profile import (
    BrokerCancelRequest,
    BrokerOrderStateProfile,
    BrokerReplaceRequest,
)
from .broker_order_profile import BrokerOrderRequest


class BrokerOrderExecutionAdapter(ABC):
    """Provider-neutral broker order execution contract."""

    @property
    @abstractmethod
    def broker_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def submit_order(
        self,
        order: BrokerOrderRequest,
    ) -> BrokerOrderStateProfile:
        raise NotImplementedError

    @abstractmethod
    def cancel_order(
        self,
        request: BrokerCancelRequest,
    ) -> BrokerOrderStateProfile:
        raise NotImplementedError

    @abstractmethod
    def replace_order(
        self,
        request: BrokerReplaceRequest,
    ) -> BrokerOrderStateProfile:
        raise NotImplementedError

    @abstractmethod
    def get_order(
        self,
        broker_order_id: str,
    ) -> BrokerOrderStateProfile | None:
        raise NotImplementedError

    @abstractmethod
    def list_orders(
        self,
        account_id: str | None = None,
    ) -> tuple[BrokerOrderStateProfile, ...]:
        raise NotImplementedError

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .broker_execution_adapter import BrokerOrderExecutionAdapter
from .broker_reconciliation_engine import (
    BrokerPositionReconciliationEngine,
)
from .broker_reconciliation_policy import BrokerReconciliationPolicy
from .broker_status_engine import BrokerOrderStatusEngine
from .broker_status_profile import (
    BrokerFillEvent,
    BrokerOrderStatusEvent,
    BrokerPositionProfile,
    BrokerReconciliationSummary,
)
from .broker_position_engine import BrokerPositionEngine


class BrokerStatusReconciliationService:
    """Coordinate status events, fills, positions, and reconciliation."""

    def __init__(
        self,
        execution_adapter: BrokerOrderExecutionAdapter,
        *,
        policy: BrokerReconciliationPolicy | None = None,
    ) -> None:
        self.execution_adapter = execution_adapter
        self.policy = policy or BrokerReconciliationPolicy()
        self.status_engine = BrokerOrderStatusEngine(self.policy)
        self.position_engine = BrokerPositionEngine()
        self.reconciliation_engine = BrokerPositionReconciliationEngine(
            self.policy
        )
        self._fills: list[BrokerFillEvent] = []
        self._status_events: list[BrokerOrderStatusEvent] = []

    def ingest_fill(self, event: BrokerFillEvent) -> tuple[str, ...]:
        state = self.execution_adapter.get_order(event.broker_order_id)
        if state is None:
            return ("BROKER_ORDER_NOT_FOUND",)
        reasons = self.status_engine.validate_fill_event(state, event)
        if not reasons:
            duplicate = any(
                existing.execution_id == event.execution_id
                for existing in self._fills
            )
            if duplicate:
                return ("DUPLICATE_EXECUTION_ID",)
            self._fills.append(event)
        return reasons

    def ingest_status(
        self,
        event: BrokerOrderStatusEvent,
    ) -> tuple[str, ...]:
        state = self.execution_adapter.get_order(event.broker_order_id)
        if state is None:
            return ("BROKER_ORDER_NOT_FOUND",)
        reasons = self.status_engine.validate_status_event(state, event)
        if not reasons:
            self._status_events.append(event)
        return reasons

    def fills(
        self,
        broker_order_id: str | None = None,
    ) -> tuple[BrokerFillEvent, ...]:
        events = self._fills
        if broker_order_id is not None:
            events = [
                event
                for event in events
                if event.broker_order_id == broker_order_id
            ]
        return tuple(events)

    def status_events(
        self,
        broker_order_id: str | None = None,
    ) -> tuple[BrokerOrderStatusEvent, ...]:
        events = self._status_events
        if broker_order_id is not None:
            events = [
                event
                for event in events
                if event.broker_order_id == broker_order_id
            ]
        return tuple(events)

    def order_summaries(self, account_id: str | None = None):
        summaries = []
        for state in self.execution_adapter.list_orders(account_id):
            summaries.append(
                self.status_engine.summarize(
                    state,
                    self.fills(state.broker_order_id),
                    self.status_events(state.broker_order_id),
                )
            )
        return tuple(summaries)

    def broker_positions(
        self,
        *,
        account_id: str,
        asset_class_by_symbol: dict[str, str] | None = None,
        multiplier_by_symbol: dict[str, int] | None = None,
    ) -> tuple[BrokerPositionProfile, ...]:
        return self.position_engine.build_positions(
            self._fills,
            broker=self.execution_adapter.broker_name,
            account_id=account_id,
            asset_class_by_symbol=asset_class_by_symbol,
            multiplier_by_symbol=multiplier_by_symbol,
        )

    def reconcile(
        self,
        *,
        account_id: str,
        platform_positions: tuple[BrokerPositionProfile, ...],
        asset_class_by_symbol: dict[str, str] | None = None,
        multiplier_by_symbol: dict[str, int] | None = None,
    ) -> BrokerReconciliationSummary:
        broker_positions = self.broker_positions(
            account_id=account_id,
            asset_class_by_symbol=asset_class_by_symbol,
            multiplier_by_symbol=multiplier_by_symbol,
        )
        summaries = self.order_summaries(account_id)
        return self.reconciliation_engine.reconcile_many(
            broker_positions,
            platform_positions,
            order_summaries=summaries,
            fill_count=len(self._fills),
        )

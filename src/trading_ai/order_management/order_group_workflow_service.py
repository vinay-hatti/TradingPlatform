from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any

from trading_ai.broker.broker_execution_profile import (
    BrokerCancelRequest,
    BrokerReplaceRequest,
)
from trading_ai.broker.broker_execution_service import BrokerExecutionService

from .order_broker_mapper import canonical_to_broker_order
from .order_group_repository import JsonOrderGroupRepository
from .order_linkage_policy import OrderLinkagePolicy
from .order_linkage_profile import (
    OrderGroupWorkflowResult,
    OrderRecoveryCheckpoint,
)
from .order_persistence_service import OrderPersistenceService
from .order_profile import CanonicalOrderCommand
from .order_recovery_service import OrderRecoveryService
from .order_repository import JsonOrderRepository
from .order_service import CanonicalOrderService


class OrderGroupWorkflowService:
    def __init__(
        self,
        *,
        repository: JsonOrderRepository,
        persistence: OrderPersistenceService,
        group_repository: JsonOrderGroupRepository,
        recovery_service: OrderRecoveryService,
        lifecycle_service: CanonicalOrderService,
        broker_execution_services: dict[str, BrokerExecutionService],
        policy: OrderLinkagePolicy | None = None,
    ) -> None:
        self.repository = repository
        self.persistence = persistence
        self.group_repository = group_repository
        self.recovery = recovery_service
        self.lifecycle = lifecycle_service
        self.broker_execution_services = broker_execution_services
        self.policy = policy or OrderLinkagePolicy()
        self.policy.validate()

    @staticmethod
    def _event_id(prefix: str) -> str:
        return f"evt-{prefix}-{uuid.uuid4().hex}"

    def activate_children(
        self,
        *,
        group_id: str,
        parent_aggregate_id: str,
    ) -> OrderGroupWorkflowResult:
        group = self.group_repository.require(group_id)
        parent = self.repository.require(parent_aggregate_id)

        activation_allowed = (
            parent.state == "FILLED"
            and self.policy.activate_children_on_parent_fill
        ) or (
            parent.state == "PARTIALLY_FILLED"
            and self.policy.activate_children_on_parent_partial_fill
        )
        if not activation_allowed:
            return OrderGroupWorkflowResult(
                valid=True,
                allowed=False,
                action="ACTIVATE_CHILDREN",
                group_id=group_id,
                aggregate_ids=(parent_aggregate_id,),
                recommendation="WAIT",
                rejection_reasons=("PARENT_ACTIVATION_STATE_NOT_REACHED",),
            )

        updated_members = []
        activated_ids = []
        for member in group.members:
            if member.role in {"CHILD", "TAKE_PROFIT", "STOP_LOSS"}:
                updated_members.append(
                    replace(member, activation_state="ACTIVE")
                )
                activated_ids.append(member.aggregate_id)
            else:
                updated_members.append(member)

        updated_group = replace(
            group,
            members=tuple(updated_members),
        )
        self.group_repository.save(updated_group)
        return OrderGroupWorkflowResult(
            valid=True,
            allowed=True,
            action="ACTIVATE_CHILDREN",
            group_id=group_id,
            aggregate_ids=tuple(activated_ids),
            recommendation="ROUTE_CHILDREN",
        )

    def cancel_oco_siblings(
        self,
        *,
        group_id: str,
        triggering_aggregate_id: str,
        route_id: str,
    ) -> OrderGroupWorkflowResult:
        group = self.group_repository.require(group_id)
        if group.group_type != "OCO":
            return OrderGroupWorkflowResult(
                valid=True,
                allowed=False,
                action="CANCEL_OCO_SIBLINGS",
                group_id=group_id,
                aggregate_ids=(triggering_aggregate_id,),
                recommendation="REJECT",
                rejection_reasons=("OCO_GROUP_REQUIRED",),
            )

        trigger = self.repository.require(triggering_aggregate_id)
        should_cancel = (
            trigger.state == "FILLED"
            and self.policy.cancel_oco_siblings_on_fill
        ) or (
            trigger.state == "PARTIALLY_FILLED"
            and self.policy.cancel_oco_siblings_on_partial_fill
        )
        if not should_cancel:
            return OrderGroupWorkflowResult(
                valid=True,
                allowed=False,
                action="CANCEL_OCO_SIBLINGS",
                group_id=group_id,
                aggregate_ids=(triggering_aggregate_id,),
                recommendation="WAIT",
                rejection_reasons=("OCO_TRIGGER_STATE_NOT_REACHED",),
            )

        broker_service = self.broker_execution_services[route_id]
        broker_results = []
        persistence_results = []
        canceled_ids = []

        for member in group.members:
            if member.aggregate_id == triggering_aggregate_id:
                continue
            aggregate = self.repository.require(member.aggregate_id)
            if aggregate.terminal:
                continue
            if aggregate.broker_order_id:
                broker_result = broker_service.cancel(
                    BrokerCancelRequest(
                        broker_order_id=aggregate.broker_order_id,
                        account_id=aggregate.account_id,
                        client_request_id=f"oco-cancel-{uuid.uuid4().hex}",
                        idempotency_key=f"oco-{group_id}-{member.aggregate_id}",
                        reason="OCO_SIBLING_FILLED",
                    )
                )
                broker_results.append(broker_result)
                if not broker_result.allowed:
                    continue

            cancel_pending = self.lifecycle.transition(
                aggregate,
                "CANCEL_REQUEST",
                event_id=self._event_id("oco-cancel-request"),
                reason="OCO_SIBLING_FILLED",
            )
            if not cancel_pending.allowed or cancel_pending.aggregate is None or cancel_pending.event is None:
                continue
            persisted = self.persistence.persist_transition(
                cancel_pending.aggregate,
                cancel_pending.event,
                expected_version=aggregate.version,
                actor="order-group-workflow",
            )
            persistence_results.append(persisted)

            canceled = self.lifecycle.transition(
                cancel_pending.aggregate,
                "CANCEL",
                event_id=self._event_id("oco-cancel"),
                reason="OCO_SIBLING_FILLED",
            )
            if canceled.allowed and canceled.aggregate is not None and canceled.event is not None:
                persisted = self.persistence.persist_transition(
                    canceled.aggregate,
                    canceled.event,
                    expected_version=cancel_pending.aggregate.version,
                    actor="order-group-workflow",
                )
                persistence_results.append(persisted)
                canceled_ids.append(member.aggregate_id)

        return OrderGroupWorkflowResult(
            valid=True,
            allowed=True,
            action="CANCEL_OCO_SIBLINGS",
            group_id=group_id,
            aggregate_ids=tuple(canceled_ids),
            recommendation="MONITOR",
            broker_results=tuple(broker_results),
            persistence_results=tuple(persistence_results),
        )

    def replace_order(
        self,
        *,
        aggregate_id: str,
        route_id: str,
        instrument_mappings: dict[str, object],
        new_limit_price: float | None,
        new_stop_price: float | None,
    ) -> OrderGroupWorkflowResult:
        aggregate = self.repository.require(aggregate_id)
        checkpoint = OrderRecoveryCheckpoint(
            checkpoint_id=f"recovery-{uuid.uuid4().hex}",
            aggregate_id=aggregate_id,
            aggregate_version=aggregate.version,
            workflow_action="REPLACE",
            state="IN_PROGRESS",
            broker_order_id=aggregate.broker_order_id,
            route_id=route_id,
            completed_steps=(),
            pending_steps=(
                "CANONICAL_REPLACE_REQUEST",
                "BROKER_REPLACE",
                "CANONICAL_REPLACE_COMPLETE",
            ),
        )
        self.recovery.save(checkpoint)

        try:
            replace_pending = self.lifecycle.transition(
                aggregate,
                "REPLACE_REQUEST",
                event_id=self._event_id("replace-request"),
                reason="USER_REQUEST",
            )
            if not replace_pending.allowed or replace_pending.aggregate is None or replace_pending.event is None:
                return OrderGroupWorkflowResult(
                    valid=True,
                    allowed=False,
                    action="REPLACE",
                    group_id=None,
                    aggregate_ids=(aggregate_id,),
                    recommendation="REJECT",
                    recovery_checkpoint=checkpoint,
                    rejection_reasons=replace_pending.rejection_reasons,
                )
            self.persistence.persist_transition(
                replace_pending.aggregate,
                replace_pending.event,
                expected_version=aggregate.version,
                actor="order-group-workflow",
            )
            checkpoint = self.recovery.mark_completed(
                checkpoint.checkpoint_id,
                "CANONICAL_REPLACE_REQUEST",
            )

            replacement = replace(
                replace_pending.aggregate,
                client_order_id=f"{aggregate.client_order_id}-r{aggregate.replace_count + 1}",
                idempotency_key=f"{aggregate.idempotency_key}-r{aggregate.replace_count + 1}",
                limit_price=new_limit_price,
                stop_price=new_stop_price,
            )
            broker_order = canonical_to_broker_order(
                replacement,
                instrument_mappings,
            )
            broker_result = self.broker_execution_services[route_id].replace(
                BrokerReplaceRequest(
                    broker_order_id=aggregate.broker_order_id or "",
                    replacement_order=broker_order,
                    client_request_id=f"replace-{uuid.uuid4().hex}",
                    idempotency_key=f"replace-{aggregate.aggregate_id}-{aggregate.version}",
                    reason="USER_REQUEST",
                )
            )
            if not broker_result.allowed:
                checkpoint = self.recovery.mark_failed(
                    checkpoint.checkpoint_id,
                    ",".join(broker_result.rejection_reasons),
                )
                return OrderGroupWorkflowResult(
                    valid=True,
                    allowed=False,
                    action="REPLACE",
                    group_id=None,
                    aggregate_ids=(aggregate_id,),
                    recommendation="RECOVER",
                    broker_results=(broker_result,),
                    recovery_checkpoint=checkpoint,
                    rejection_reasons=broker_result.rejection_reasons,
                )
            checkpoint = self.recovery.mark_completed(
                checkpoint.checkpoint_id,
                "BROKER_REPLACE",
            )

            completed = self.lifecycle.transition(
                replace_pending.aggregate,
                "REPLACE",
                event_id=self._event_id("replace-complete"),
                broker_order_id=broker_result.broker_order_id,
                reason="USER_REQUEST",
                metadata={
                    "previous_broker_order_id": aggregate.broker_order_id,
                },
            )
            assert completed.aggregate is not None and completed.event is not None
            persisted = self.persistence.persist_transition(
                completed.aggregate,
                completed.event,
                expected_version=replace_pending.aggregate.version,
                actor="order-group-workflow",
            )
            checkpoint = self.recovery.mark_completed(
                checkpoint.checkpoint_id,
                "CANONICAL_REPLACE_COMPLETE",
            )
            return OrderGroupWorkflowResult(
                valid=True,
                allowed=True,
                action="REPLACE",
                group_id=None,
                aggregate_ids=(aggregate_id,),
                recommendation="MONITOR",
                broker_results=(broker_result,),
                persistence_results=(persisted,),
                recovery_checkpoint=checkpoint,
            )
        except Exception as exc:
            checkpoint = self.recovery.mark_failed(
                checkpoint.checkpoint_id,
                str(exc),
            )
            return OrderGroupWorkflowResult(
                valid=True,
                allowed=False,
                action="REPLACE",
                group_id=None,
                aggregate_ids=(aggregate_id,),
                recommendation="RECOVER",
                recovery_checkpoint=checkpoint,
                rejection_reasons=("WORKFLOW_EXCEPTION",),
                metadata={"error": str(exc)},
            )

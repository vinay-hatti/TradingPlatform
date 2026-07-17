from __future__ import annotations

import uuid

from trading_ai.broker.broker_execution_profile import (
    BrokerCancelRequest,
    BrokerReplaceRequest,
)
from trading_ai.broker.broker_execution_service import BrokerExecutionService

from .order_broker_mapper import canonical_to_broker_order
from .order_command_handler import OrderCommandHandler
from .order_execution_router import OrderExecutionRouter
from .order_persistence_service import OrderPersistenceService
from .order_profile import CanonicalOrderCommand
from .order_repository import JsonOrderRepository
from .order_routing_policy import OrderRoutingPolicy
from .order_routing_profile import OrderWorkflowResult


class OrderWorkflowService:
    """Orchestrate canonical order lifecycle, persistence, routing, and broker execution."""

    def __init__(
        self,
        *,
        command_handler: OrderCommandHandler,
        persistence_service: OrderPersistenceService,
        router: OrderExecutionRouter,
        broker_execution_services: dict[str, BrokerExecutionService],
        repository: JsonOrderRepository,
        routing_policy: OrderRoutingPolicy | None = None,
    ) -> None:
        self.command_handler = command_handler
        self.persistence = persistence_service
        self.router = router
        self.broker_execution_services = broker_execution_services
        self.repository = repository
        self.policy = routing_policy or OrderRoutingPolicy()
        self.policy.validate()

    def _event_id(self, prefix: str) -> str:
        return f"evt-{prefix}-{uuid.uuid4().hex}"

    def create(self, command: CanonicalOrderCommand) -> OrderWorkflowResult:
        transition = self.command_handler.handle(command)
        if not transition.allowed or transition.aggregate is None or transition.event is None:
            return OrderWorkflowResult(
                valid=True,
                allowed=False,
                action="CREATE",
                aggregate_id=command.aggregate_id,
                state="UNKNOWN",
                aggregate_version=0,
                recommendation="REJECT",
                rejection_reasons=transition.rejection_reasons,
            )

        persisted = self.persistence.persist_created(
            transition.aggregate,
            transition.event,
            actor="order-workflow",
        )
        return OrderWorkflowResult(
            valid=True,
            allowed=True,
            action="CREATE",
            aggregate_id=transition.aggregate.aggregate_id,
            state=transition.aggregate.state,
            aggregate_version=transition.aggregate.version,
            persistence_result=persisted,
            recommendation="CONTINUE",
        )

    def validate_and_route(
        self,
        aggregate_id: str,
        *,
        requested_route: str | None = None,
    ) -> OrderWorkflowResult:
        aggregate = self.repository.require(aggregate_id)

        validate_command = CanonicalOrderCommand(
            command_id=f"cmd-validate-{uuid.uuid4().hex}",
            command_type="VALIDATE",
            aggregate_id=aggregate.aggregate_id,
            client_order_id=aggregate.client_order_id,
            account_id=aggregate.account_id,
            idempotency_key=aggregate.idempotency_key,
            order_type=aggregate.order_type,
            time_in_force=aggregate.time_in_force,
            legs=aggregate.legs,
            limit_price=aggregate.limit_price,
            stop_price=aggregate.stop_price,
            correlation_id=aggregate.aggregate_id,
            causation_id=aggregate.last_event_id,
        )
        validated = self.command_handler.handle(
            validate_command,
            aggregate=aggregate,
            event_id=self._event_id("validate"),
        )
        if not validated.allowed or validated.aggregate is None or validated.event is None:
            return OrderWorkflowResult(
                valid=True,
                allowed=False,
                action="VALIDATE",
                aggregate_id=aggregate_id,
                state=aggregate.state,
                aggregate_version=aggregate.version,
                recommendation="REJECT",
                rejection_reasons=validated.rejection_reasons,
            )
        self.persistence.persist_transition(
            validated.aggregate,
            validated.event,
            expected_version=aggregate.version,
            actor="order-workflow",
        )

        routing = self.router.select(
            validated.aggregate,
            requested_route=requested_route,
        )
        if not routing.allowed:
            return OrderWorkflowResult(
                valid=True,
                allowed=False,
                action="ROUTE",
                aggregate_id=aggregate_id,
                state=validated.aggregate.state,
                aggregate_version=validated.aggregate.version,
                routing_decision=routing,
                recommendation="REJECT",
                rejection_reasons=routing.rejection_reasons,
            )

        route_command = CanonicalOrderCommand(
            command_id=f"cmd-route-{uuid.uuid4().hex}",
            command_type="ROUTE",
            aggregate_id=aggregate_id,
            client_order_id=validated.aggregate.client_order_id,
            account_id=validated.aggregate.account_id,
            idempotency_key=validated.aggregate.idempotency_key,
            order_type=validated.aggregate.order_type,
            time_in_force=validated.aggregate.time_in_force,
            legs=validated.aggregate.legs,
            limit_price=validated.aggregate.limit_price,
            stop_price=validated.aggregate.stop_price,
            correlation_id=aggregate_id,
            causation_id=validated.event.event_id,
            metadata={"route_id": routing.route_id, "broker": routing.broker},
        )
        routed = self.command_handler.handle(
            route_command,
            aggregate=validated.aggregate,
            event_id=self._event_id("route"),
        )
        assert routed.aggregate is not None and routed.event is not None
        persisted = self.persistence.persist_transition(
            routed.aggregate,
            routed.event,
            expected_version=validated.aggregate.version,
            actor="order-workflow",
        )

        return OrderWorkflowResult(
            valid=True,
            allowed=True,
            action="ROUTE",
            aggregate_id=aggregate_id,
            state=routed.aggregate.state,
            aggregate_version=routed.aggregate.version,
            routing_decision=routing,
            persistence_result=persisted,
            recommendation="SUBMIT",
        )

    def submit(
        self,
        aggregate_id: str,
        *,
        route_id: str,
        instrument_mappings: dict[str, object],
    ) -> OrderWorkflowResult:
        aggregate = self.repository.require(aggregate_id)
        if self.policy.require_routed_state_before_submission and aggregate.state != "ROUTED":
            return OrderWorkflowResult(
                valid=True,
                allowed=False,
                action="SUBMIT",
                aggregate_id=aggregate_id,
                state=aggregate.state,
                aggregate_version=aggregate.version,
                recommendation="REJECT",
                rejection_reasons=("ROUTED_STATE_REQUIRED",),
            )

        broker_service = self.broker_execution_services.get(route_id)
        if broker_service is None:
            return OrderWorkflowResult(
                valid=True,
                allowed=False,
                action="SUBMIT",
                aggregate_id=aggregate_id,
                state=aggregate.state,
                aggregate_version=aggregate.version,
                recommendation="REJECT",
                rejection_reasons=("BROKER_ROUTE_SERVICE_NOT_FOUND",),
            )

        broker_order = canonical_to_broker_order(
            aggregate,
            instrument_mappings,
        )
        broker_result = broker_service.submit(broker_order)
        if not broker_result.allowed:
            return OrderWorkflowResult(
                valid=True,
                allowed=False,
                action="SUBMIT",
                aggregate_id=aggregate_id,
                state=aggregate.state,
                aggregate_version=aggregate.version,
                broker_result=broker_result,
                recommendation="REJECT",
                rejection_reasons=broker_result.rejection_reasons,
            )

        submit_command = CanonicalOrderCommand(
            command_id=f"cmd-submit-{uuid.uuid4().hex}",
            command_type="SUBMIT",
            aggregate_id=aggregate_id,
            client_order_id=aggregate.client_order_id,
            account_id=aggregate.account_id,
            idempotency_key=aggregate.idempotency_key,
            order_type=aggregate.order_type,
            time_in_force=aggregate.time_in_force,
            legs=aggregate.legs,
            limit_price=aggregate.limit_price,
            stop_price=aggregate.stop_price,
            correlation_id=aggregate_id,
            causation_id=aggregate.last_event_id,
            metadata={"route_id": route_id},
        )
        submitted = self.command_handler.handle(
            submit_command,
            aggregate=aggregate,
            event_id=self._event_id("submit"),
            broker_order_id=broker_result.broker_order_id,
        )
        assert submitted.aggregate is not None and submitted.event is not None
        persisted = self.persistence.persist_transition(
            submitted.aggregate,
            submitted.event,
            expected_version=aggregate.version,
            actor="order-workflow",
        )
        return OrderWorkflowResult(
            valid=True,
            allowed=True,
            action="SUBMIT",
            aggregate_id=aggregate_id,
            state=submitted.aggregate.state,
            aggregate_version=submitted.aggregate.version,
            broker_result=broker_result,
            persistence_result=persisted,
            recommendation="MONITOR",
        )

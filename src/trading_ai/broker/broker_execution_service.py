from __future__ import annotations

from dataclasses import asdict

from .broker_error import BrokerAdapterError, normalize_broker_error
from .broker_execution_adapter import BrokerOrderExecutionAdapter
from .broker_execution_engine import BrokerExecutionEngine
from .broker_execution_policy import BrokerExecutionPolicy
from .broker_execution_profile import (
    BrokerCancelRequest,
    BrokerOrderExecutionResult,
    BrokerReplaceRequest,
    IdempotencyRecordProfile,
)
from .broker_idempotency_registry import (
    BrokerIdempotencyRegistry,
    canonical_request_hash,
)
from .broker_order_profile import BrokerOrderRequest
from .broker_order_service import BrokerOrderService
from .broker_service import BrokerService


class BrokerExecutionService:
    """Validate, submit, cancel, replace, and replay broker requests safely."""

    def __init__(
        self,
        *,
        broker_service: BrokerService,
        execution_adapter: BrokerOrderExecutionAdapter,
        order_service: BrokerOrderService | None = None,
        policy: BrokerExecutionPolicy | None = None,
        idempotency_registry: BrokerIdempotencyRegistry | None = None,
    ) -> None:
        self.broker_service = broker_service
        self.execution_adapter = execution_adapter
        self.order_service = order_service or BrokerOrderService()
        self.policy = policy or BrokerExecutionPolicy()
        self.engine = BrokerExecutionEngine(self.policy)
        self.registry = (
            idempotency_registry
            or BrokerIdempotencyRegistry()
        )

    def _cached_result(
        self,
        *,
        key: str,
        action: str,
        request_hash: str,
    ) -> BrokerOrderExecutionResult | None:
        record = self.registry.get(key)
        if record is None:
            return None

        if record.action != action:
            return self.engine.evaluate(
                action=action,
                broker=self.execution_adapter.broker_name,
                client_order_id=record.client_order_id or "",
                idempotency_key=key,
                replayed=True,
                extra_checks=(
                    (
                        "idempotency_action_match",
                        False,
                        "Idempotency key was used for another action.",
                    ),
                ),
            )

        if (
            self.policy.reject_payload_mismatch_on_replay
            and record.request_hash != request_hash
        ):
            return self.engine.evaluate(
                action=action,
                broker=self.execution_adapter.broker_name,
                client_order_id=record.client_order_id or "",
                idempotency_key=key,
                replayed=True,
                extra_checks=(
                    (
                        "idempotency_payload_match",
                        False,
                        "Idempotency replay payload does not match.",
                    ),
                ),
            )

        if not self.policy.allow_idempotent_replay:
            return self.engine.evaluate(
                action=action,
                broker=self.execution_adapter.broker_name,
                client_order_id=record.client_order_id or "",
                idempotency_key=key,
                replayed=True,
                extra_checks=(
                    (
                        "idempotent_replay",
                        False,
                        "Idempotent replay is disabled.",
                    ),
                ),
            )

        state = (
            self.execution_adapter.get_order(record.broker_order_id)
            if record.broker_order_id
            else None
        )
        readiness = self.broker_service.readiness()
        return self.engine.evaluate(
            action=action,
            broker=self.execution_adapter.broker_name,
            client_order_id=record.client_order_id or "",
            idempotency_key=key,
            readiness=readiness,
            order_state=state,
            replayed=True,
            extra_checks=(
                (
                    "idempotency_payload_match",
                    True,
                    "Idempotency payload matches cached request.",
                ),
            ),
            metadata={
                "cached_record_status": record.status,
                "cached_result": record.result,
            },
        )

    def _persist_result(
        self,
        *,
        key: str,
        action: str,
        request_hash: str,
        result: BrokerOrderExecutionResult,
        persist: bool,
    ) -> None:
        record = IdempotencyRecordProfile(
            key=key,
            action=action,
            request_hash=request_hash,
            broker_order_id=result.broker_order_id,
            client_order_id=result.client_order_id,
            status=result.status,
            result=result.to_dict(),
        )
        self.registry.register(record)
        if persist:
            self.registry.save()

    def submit(
        self,
        order: BrokerOrderRequest,
        *,
        persist: bool = True,
    ) -> BrokerOrderExecutionResult:
        key = order.idempotency_key or ""
        request_hash = canonical_request_hash(order)

        if key:
            cached = self._cached_result(
                key=key,
                action="SUBMIT",
                request_hash=request_hash,
            )
            if cached is not None:
                return cached

        readiness = self.broker_service.readiness()
        validation = self.order_service.validate(
            order,
            reserve_client_order_id=True,
        )

        preflight = self.engine.evaluate(
            action="SUBMIT",
            broker=self.execution_adapter.broker_name,
            client_order_id=order.client_order_id,
            idempotency_key=key,
            readiness=readiness,
            validation=validation,
        )
        if not preflight.allowed:
            return preflight

        try:
            state = self.execution_adapter.submit_order(order)
        except Exception as exc:
            raise BrokerAdapterError(
                normalize_broker_error(
                    self.execution_adapter.broker_name,
                    exc,
                    category="ORDER_SUBMISSION",
                    retryable=True,
                )
            ) from exc

        result = self.engine.evaluate(
            action="SUBMIT",
            broker=self.execution_adapter.broker_name,
            client_order_id=order.client_order_id,
            idempotency_key=key,
            readiness=readiness,
            validation=validation,
            order_state=state,
        )

        if key:
            self._persist_result(
                key=key,
                action="SUBMIT",
                request_hash=request_hash,
                result=result,
                persist=persist,
            )

        return result

    def cancel(
        self,
        request: BrokerCancelRequest,
        *,
        persist: bool = True,
    ) -> BrokerOrderExecutionResult:
        request_hash = canonical_request_hash(request)
        cached = self._cached_result(
            key=request.idempotency_key,
            action="CANCEL",
            request_hash=request_hash,
        )
        if cached is not None:
            return cached

        readiness = self.broker_service.readiness()
        current = self.execution_adapter.get_order(
            request.broker_order_id
        )

        exists = current is not None
        status = current.status if current is not None else "UNKNOWN"
        cancellable = (
            exists
            and (
                status in self.policy.cancellable_statuses
                or (
                    self.policy.allow_cancel_terminal_orders
                    and status in self.policy.terminal_statuses
                )
            )
        )

        preflight = self.engine.evaluate(
            action="CANCEL",
            broker=self.execution_adapter.broker_name,
            client_order_id=(
                current.client_order_id
                if current is not None
                else request.client_request_id
            ),
            idempotency_key=request.idempotency_key,
            readiness=readiness,
            order_state=current,
            extra_checks=(
                (
                    "order_exists",
                    exists,
                    "Broker order must exist.",
                ),
                (
                    "order_cancellable",
                    cancellable,
                    "Broker order status must be cancellable.",
                ),
            ),
        )
        if not preflight.allowed:
            return preflight

        try:
            state = self.execution_adapter.cancel_order(request)
        except Exception as exc:
            raise BrokerAdapterError(
                normalize_broker_error(
                    self.execution_adapter.broker_name,
                    exc,
                    category="ORDER_CANCELLATION",
                    retryable=True,
                )
            ) from exc

        result = self.engine.evaluate(
            action="CANCEL",
            broker=self.execution_adapter.broker_name,
            client_order_id=state.client_order_id,
            idempotency_key=request.idempotency_key,
            readiness=readiness,
            order_state=state,
            extra_checks=(
                (
                    "order_exists",
                    True,
                    "Broker order exists.",
                ),
                (
                    "order_cancellable",
                    True,
                    "Broker order status was cancellable.",
                ),
            ),
        )

        self._persist_result(
            key=request.idempotency_key,
            action="CANCEL",
            request_hash=request_hash,
            result=result,
            persist=persist,
        )
        return result

    def replace(
        self,
        request: BrokerReplaceRequest,
        *,
        persist: bool = True,
    ) -> BrokerOrderExecutionResult:
        request_hash = canonical_request_hash(request)
        cached = self._cached_result(
            key=request.idempotency_key,
            action="REPLACE",
            request_hash=request_hash,
        )
        if cached is not None:
            return cached

        readiness = self.broker_service.readiness()
        current = self.execution_adapter.get_order(
            request.broker_order_id
        )
        validation = self.order_service.validate(
            request.replacement_order,
            reserve_client_order_id=True,
        )

        exists = current is not None
        status = current.status if current is not None else "UNKNOWN"
        replaceable = (
            exists
            and (
                status in self.policy.replaceable_statuses
                or (
                    self.policy.allow_replace_terminal_orders
                    and status in self.policy.terminal_statuses
                )
            )
        )
        replace_count_ok = (
            current is not None
            and current.replace_count < self.policy.maximum_replace_count
        )

        preflight = self.engine.evaluate(
            action="REPLACE",
            broker=self.execution_adapter.broker_name,
            client_order_id=request.replacement_order.client_order_id,
            idempotency_key=request.idempotency_key,
            readiness=readiness,
            validation=validation,
            order_state=current,
            extra_checks=(
                (
                    "order_exists",
                    exists,
                    "Broker order must exist.",
                ),
                (
                    "order_replaceable",
                    replaceable,
                    "Broker order status must be replaceable.",
                ),
                (
                    "replace_count",
                    replace_count_ok,
                    "Maximum replacement count must not be exceeded.",
                ),
            ),
        )
        if not preflight.allowed:
            return preflight

        try:
            state = self.execution_adapter.replace_order(request)
        except Exception as exc:
            raise BrokerAdapterError(
                normalize_broker_error(
                    self.execution_adapter.broker_name,
                    exc,
                    category="ORDER_REPLACEMENT",
                    retryable=True,
                )
            ) from exc

        result = self.engine.evaluate(
            action="REPLACE",
            broker=self.execution_adapter.broker_name,
            client_order_id=state.client_order_id,
            idempotency_key=request.idempotency_key,
            readiness=readiness,
            validation=validation,
            order_state=state,
            extra_checks=(
                (
                    "order_exists",
                    True,
                    "Broker order exists.",
                ),
                (
                    "order_replaceable",
                    True,
                    "Broker order status was replaceable.",
                ),
                (
                    "replace_count",
                    True,
                    "Replacement count is within policy.",
                ),
            ),
            metadata={
                "replaced_broker_order_id": request.broker_order_id,
            },
        )

        self._persist_result(
            key=request.idempotency_key,
            action="REPLACE",
            request_hash=request_hash,
            result=result,
            persist=persist,
        )
        return result

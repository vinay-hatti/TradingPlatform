"""Canonical order management foundation."""
from .order_aggregate_engine import CanonicalOrderAggregateEngine
from .order_event_contracts import ORDER_COMMAND_TYPES, ORDER_EVENT_TYPES, OrderLifecycleEventEnvelope
from .order_policy import OrderLifecyclePolicy
from .order_profile import (
    CanonicalOrderAggregate, CanonicalOrderCommand, CanonicalOrderEvent,
    CanonicalOrderLeg, OrderTransitionCheck, OrderTransitionResult,
)
from .order_service import CanonicalOrderService
from .order_state_machine import OrderLifecycleStateMachine

__all__ = [
    "CanonicalOrderAggregate", "CanonicalOrderAggregateEngine",
    "CanonicalOrderCommand", "CanonicalOrderEvent", "CanonicalOrderLeg",
    "CanonicalOrderService", "ORDER_COMMAND_TYPES", "ORDER_EVENT_TYPES",
    "OrderLifecycleEventEnvelope", "OrderLifecyclePolicy",
    "OrderLifecycleStateMachine", "OrderTransitionCheck", "OrderTransitionResult",
]
"""Optional exports for Milestone 30 Phase 4 Step 2."""

from .order_audit_ledger import OrderAuditLedger
from .order_event_journal import OrderEventJournal
from .order_persistence_service import OrderPersistenceService
from .order_repository import JsonOrderRepository
from .order_repository_exceptions import (
    AuditLedgerIntegrityError,
    DuplicateOrderError,
    DuplicateOrderEventError,
    OptimisticConcurrencyError,
    OrderNotFoundError,
    OrderRepositoryError,
)
from .order_repository_policy import OrderRepositoryPolicy
from .order_repository_profile import (
    OrderAuditEntry,
    OrderJournalReplayResult,
    OrderPersistenceResult,
    OrderRepositoryRecord,
)

__all__ = [
    "AuditLedgerIntegrityError",
    "DuplicateOrderError",
    "DuplicateOrderEventError",
    "JsonOrderRepository",
    "OptimisticConcurrencyError",
    "OrderAuditEntry",
    "OrderAuditLedger",
    "OrderEventJournal",
    "OrderJournalReplayResult",
    "OrderNotFoundError",
    "OrderPersistenceResult",
    "OrderPersistenceService",
    "OrderRepositoryError",
    "OrderRepositoryPolicy",
    "OrderRepositoryRecord",
]
"""Optional exports for Milestone 30 Phase 4 Step 3."""

from .order_broker_mapper import canonical_to_broker_order
from .order_command_handler import OrderCommandHandler
from .order_execution_router import OrderExecutionRouter
from .order_routing_policy import OrderRoutingPolicy
from .order_routing_profile import (
    OrderRouteCandidate,
    OrderRoutingCheck,
    OrderRoutingDecision,
    OrderWorkflowResult,
)
from .order_workflow_service import OrderWorkflowService

__all__ = [
    "OrderCommandHandler",
    "OrderExecutionRouter",
    "OrderRouteCandidate",
    "OrderRoutingCheck",
    "OrderRoutingDecision",
    "OrderRoutingPolicy",
    "OrderWorkflowResult",
    "OrderWorkflowService",
    "canonical_to_broker_order",
]
"""Optional exports for Milestone 30 Phase 4 Step 4."""

from .order_group_engine import OrderGroupEngine
from .order_group_repository import JsonOrderGroupRepository
from .order_group_workflow_service import OrderGroupWorkflowService
from .order_linkage_policy import OrderLinkagePolicy
from .order_linkage_profile import (
    OrderGroupDecision,
    OrderGroupProfile,
    OrderGroupWorkflowResult,
    OrderLinkMember,
    OrderLinkageCheck,
    OrderRecoveryCheckpoint,
)
from .order_recovery_service import OrderRecoveryService

__all__ = [
    "JsonOrderGroupRepository",
    "OrderGroupDecision",
    "OrderGroupEngine",
    "OrderGroupProfile",
    "OrderGroupWorkflowResult",
    "OrderGroupWorkflowService",
    "OrderLinkMember",
    "OrderLinkageCheck",
    "OrderLinkagePolicy",
    "OrderRecoveryCheckpoint",
    "OrderRecoveryService",
]
"""Optional exports for Milestone 30 Phase 4 Step 5."""

from .order_management_reporting import OrderManagementOperationalReport

__all__ = ["OrderManagementOperationalReport"]

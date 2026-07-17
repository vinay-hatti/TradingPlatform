from __future__ import annotations
from .order_aggregate_engine import CanonicalOrderAggregateEngine
from .order_policy import OrderLifecyclePolicy
from .order_profile import CanonicalOrderAggregate, CanonicalOrderCommand, OrderTransitionResult
from .order_state_machine import OrderLifecycleStateMachine

class CanonicalOrderService:
    def __init__(self, policy: OrderLifecyclePolicy | None = None) -> None:
        self.policy = policy or OrderLifecyclePolicy()
        self.aggregate_engine = CanonicalOrderAggregateEngine(self.policy)
        self.state_machine = OrderLifecycleStateMachine(self.policy)

    def create(self, command: CanonicalOrderCommand) -> OrderTransitionResult:
        return self.aggregate_engine.create(command)

    def transition(self, aggregate: CanonicalOrderAggregate, action: str, **kwargs) -> OrderTransitionResult:
        return self.state_machine.transition(aggregate, action, **kwargs)

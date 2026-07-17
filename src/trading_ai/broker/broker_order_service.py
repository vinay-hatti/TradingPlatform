from .broker_order_policy import BrokerOrderPolicy
from .broker_order_profile import BrokerOrderRequest
from .broker_order_validation_engine import BrokerOrderValidationEngine

class BrokerOrderService:
    def __init__(self, policy: BrokerOrderPolicy | None = None) -> None:
        self.engine = BrokerOrderValidationEngine(policy)
    def validate(self, order: BrokerOrderRequest, *, reserve_client_order_id: bool = False):
        return self.engine.evaluate(order, register_client_order_id=reserve_client_order_id)

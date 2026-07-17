from __future__ import annotations
from typing import Any
from .market_data_reconciliation_engine import MarketDataReconciliationEngine
from .market_data_reconciliation_policy import MarketDataReconciliationPolicy

class MarketDataReconciliationService:
    def __init__(self, policy: MarketDataReconciliationPolicy | None = None) -> None:
        self.engine = MarketDataReconciliationEngine(policy)
    def reconcile(self, live: Any, historical: Any):
        return self.engine.evaluate(live, historical)
    def reconcile_many(self, pairs):
        return self.engine.evaluate_many(pairs)

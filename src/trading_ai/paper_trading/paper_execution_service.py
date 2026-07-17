from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from .paper_execution_engine import PaperExecutionEngine
from .paper_execution_policy import PaperExecutionPolicy
from .paper_execution_profile import (
    PaperExecutionDecision,
    PaperExecutionRequest,
)
from .paper_execution_repository import JsonPaperExecutionRepository
from .paper_trading_runtime_repository import (
    JsonPaperTradingRuntimeRepository,
)


class PaperExecutionService:
    def __init__(
        self,
        *,
        policy: PaperExecutionPolicy | None = None,
        execution_repository: JsonPaperExecutionRepository | None = None,
        runtime_repository: JsonPaperTradingRuntimeRepository | None = None,
    ) -> None:
        self.policy = policy or PaperExecutionPolicy()
        self.engine = PaperExecutionEngine(self.policy)
        self.execution_repository = (
            execution_repository or JsonPaperExecutionRepository()
        )
        self.runtime_repository = runtime_repository

    def execute(
        self,
        request: PaperExecutionRequest,
    ) -> PaperExecutionDecision:
        existing = self.execution_repository.get(request.execution_key)
        if (
            existing is not None
            and self.policy.reject_duplicate_execution_key
        ):
            return PaperExecutionDecision(
                valid=True,
                allowed=True,
                execution_key=request.execution_key,
                aggregate_id=existing.aggregate_id,
                score=100.0,
                grade="A",
                severity="LOW",
                recommendation="IDEMPOTENT_REPLAY",
                record=existing,
                warnings=("DUPLICATE_EXECUTION_KEY_REPLAYED",),
            )

        decision = self.engine.evaluate(request)
        if decision.allowed and decision.record is not None:
            self.execution_repository.save(decision.record)
            if self.runtime_repository is not None:
                state = self.runtime_repository.require(
                    request.session_id
                )
                record = decision.record
                pending = tuple(
                    item for item in state.pending_order_ids
                    if item != record.aggregate_id
                )
                updated = replace(
                    state,
                    orders_submitted=state.orders_submitted + 1,
                    fills_received=state.fills_received
                    + len(record.fills),
                    pending_order_ids=pending,
                    version=state.version + 1,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
                self.runtime_repository.save(updated)
        return decision

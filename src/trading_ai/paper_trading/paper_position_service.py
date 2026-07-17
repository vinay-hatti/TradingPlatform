from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone

from .paper_adjustment_engine import PaperAdjustmentEngine
from .paper_execution_profile import PaperExecutionRecord, PaperFillProfile
from .paper_position_engine import PaperPositionEngine
from .paper_position_policy import PaperPositionPolicy
from .paper_position_repository import JsonPaperPositionRepository
from .paper_trading_runtime_repository import JsonPaperTradingRuntimeRepository

class PaperPositionService:
    def __init__(
        self,
        *,
        policy: PaperPositionPolicy | None = None,
        repository: JsonPaperPositionRepository | None = None,
        runtime_repository: JsonPaperTradingRuntimeRepository | None = None,
    ) -> None:
        self.policy = policy or PaperPositionPolicy()
        self.engine = PaperPositionEngine(self.policy)
        self.adjustments = PaperAdjustmentEngine(self.policy)
        self.repository = repository or JsonPaperPositionRepository()
        self.runtime_repository = runtime_repository

    def process_execution(
        self,
        record: PaperExecutionRecord,
        *,
        asset_class: str,
        multiplier: int,
    ):
        decision = self.engine.open_from_execution(
            record,
            asset_class=asset_class,
            multiplier=multiplier,
        )
        if decision.allowed and decision.position is not None:
            self.repository.save(decision.position)
            if self.runtime_repository is not None:
                state = self.runtime_repository.require(record.session_id)
                ids = tuple(dict.fromkeys(
                    (*state.active_position_ids, decision.position.position_id)
                ))
                updated = replace(
                    state,
                    open_positions=len(ids),
                    active_position_ids=ids,
                    version=state.version + 1,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
                self.runtime_repository.save(updated)
        return decision

    def mark(self, position_id: str, market_price: float):
        position = self.repository.get(position_id)
        if position is None:
            raise KeyError(position_id)
        updated = self.engine.mark(position, market_price)
        self.repository.save(updated)
        return updated

    def evaluate_exit(self, position_id: str):
        position = self.repository.get(position_id)
        if position is None:
            raise KeyError(position_id)
        return self.engine.evaluate_exit(position)

    def evaluate_adjustment(self, position_id: str):
        position = self.repository.get(position_id)
        if position is None:
            raise KeyError(position_id)
        return self.adjustments.evaluate(position)

    def close(self, position_id: str, fill: PaperFillProfile):
        position = self.repository.get(position_id)
        if position is None:
            raise KeyError(position_id)
        updated = self.engine.close_with_fill(position, fill)
        self.repository.save(updated)

        if self.runtime_repository is not None:
            state = self.runtime_repository.require(updated.session_id)
            active_ids = tuple(
                item for item in state.active_position_ids
                if item != position_id or updated.is_open
            )
            new_realized = state.realized_pnl + (
                updated.realized_pnl - position.realized_pnl
            )
            runtime = replace(
                state,
                open_positions=len(active_ids),
                active_position_ids=active_ids,
                realized_pnl=round(new_realized, 6),
                unrealized_pnl=round(
                    sum(
                        p.unrealized_pnl
                        for p in self.repository.open_for_session(updated.session_id)
                    ),
                    6,
                ),
                version=state.version + 1,
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            self.runtime_repository.save(runtime)
        return updated

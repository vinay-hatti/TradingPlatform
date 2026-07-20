from __future__ import annotations

from typing import Any

from .trade_construction_engine import TradeConstructionEngine
from .trade_construction_profile import TradeConstructionProfile


class TradeConstructionService:
    def __init__(
        self,
        engine: TradeConstructionEngine | None = None,
    ) -> None:
        self.engine = engine or TradeConstructionEngine()

    def construct(self, **kwargs: Any) -> TradeConstructionProfile:
        return self.engine.construct(**kwargs)

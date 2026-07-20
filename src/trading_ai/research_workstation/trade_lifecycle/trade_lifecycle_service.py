from __future__ import annotations

from typing import Any

from .trade_lifecycle_engine import TradeLifecycleEngine
from .trade_lifecycle_profile import TradeLifecycleProfile


class TradeLifecycleService:
    def __init__(
        self,
        engine: TradeLifecycleEngine | None = None,
    ) -> None:
        self.engine = engine or TradeLifecycleEngine()

    def plan(self, **kwargs: Any) -> TradeLifecycleProfile:
        return self.engine.plan(**kwargs)

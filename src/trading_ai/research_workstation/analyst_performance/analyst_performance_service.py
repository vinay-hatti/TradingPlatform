from __future__ import annotations

from typing import Any

from .analyst_performance_engine import AnalystPerformanceEngine


class AnalystPerformanceService:
    def __init__(
        self,
        engine: AnalystPerformanceEngine | None = None,
    ) -> None:
        self.engine = engine or AnalystPerformanceEngine()

    def build_scorecard(self, **kwargs: Any):
        return self.engine.build_scorecard(**kwargs)

    def build_report(self, **kwargs: Any):
        return self.engine.build_report(**kwargs)

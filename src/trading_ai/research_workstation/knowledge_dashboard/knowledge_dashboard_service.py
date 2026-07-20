from __future__ import annotations

from typing import Any

from .knowledge_dashboard_engine import KnowledgeDashboardEngine


class KnowledgeDashboardService:
    def __init__(self, engine: KnowledgeDashboardEngine | None = None) -> None:
        self.engine = engine or KnowledgeDashboardEngine()

    def build(self, **kwargs: Any):
        return self.engine.build(**kwargs)

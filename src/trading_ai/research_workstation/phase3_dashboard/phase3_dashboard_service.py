from __future__ import annotations

from typing import Any

from .phase3_dashboard_engine import Phase3DashboardEngine
from .phase3_dashboard_profile import Phase3DashboardProfile


class Phase3DashboardService:
    def __init__(
        self,
        engine: Phase3DashboardEngine | None = None,
    ) -> None:
        self.engine = engine or Phase3DashboardEngine()

    def build(self, **kwargs: Any) -> Phase3DashboardProfile:
        return self.engine.build(**kwargs)

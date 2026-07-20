from typing import Any
from .research_dashboard_engine import ResearchDashboardEngine
from .research_dashboard_profile import ResearchDashboardProfile
class ResearchDashboardService:
    def __init__(self, engine: ResearchDashboardEngine | None=None) -> None:
        self.engine=engine or ResearchDashboardEngine()
    def build(self, **kwargs: Any) -> ResearchDashboardProfile:
        return self.engine.build(**kwargs)

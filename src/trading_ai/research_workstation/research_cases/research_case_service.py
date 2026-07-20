from __future__ import annotations

from typing import Any

from .research_case_engine import ResearchCaseEngine
from .research_case_profile import ResearchCaseProfile


class ResearchCaseService:
    def __init__(
        self,
        engine: ResearchCaseEngine | None = None,
    ) -> None:
        self.engine = engine or ResearchCaseEngine()

    def build(self, **kwargs: Any) -> ResearchCaseProfile:
        return self.engine.build(**kwargs)

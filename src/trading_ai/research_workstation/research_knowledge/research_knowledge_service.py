from __future__ import annotations

from typing import Any

from .research_knowledge_engine import ResearchKnowledgeEngine
from .research_knowledge_profile import (
    KnowledgeCaseProfile,
    ResearchKnowledgeBaseProfile,
)


class ResearchKnowledgeService:
    def __init__(
        self,
        engine: ResearchKnowledgeEngine | None = None,
    ) -> None:
        self.engine = engine or ResearchKnowledgeEngine()

    def build_case(self, **kwargs: Any) -> KnowledgeCaseProfile:
        return self.engine.build_case(**kwargs)

    def build_knowledge_base(
        self,
        **kwargs: Any,
    ) -> ResearchKnowledgeBaseProfile:
        return self.engine.build_knowledge_base(**kwargs)

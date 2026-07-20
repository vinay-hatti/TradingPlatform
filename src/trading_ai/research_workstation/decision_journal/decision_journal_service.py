from __future__ import annotations

from typing import Any

from .decision_journal_engine import DecisionJournalEngine
from .decision_journal_profile import DecisionJournalProfile


class DecisionJournalService:
    def __init__(
        self,
        engine: DecisionJournalEngine | None = None,
    ) -> None:
        self.engine = engine or DecisionJournalEngine()

    def build(self, **kwargs: Any) -> DecisionJournalProfile:
        return self.engine.build(**kwargs)

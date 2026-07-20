from __future__ import annotations

from typing import Any

from .pretrade_governance_engine import PreTradeGovernanceEngine
from .pretrade_governance_profile import GovernanceDecisionProfile


class PreTradeGovernanceService:
    def __init__(
        self,
        engine: PreTradeGovernanceEngine | None = None,
    ) -> None:
        self.engine = engine or PreTradeGovernanceEngine()

    def evaluate(self, **kwargs: Any) -> GovernanceDecisionProfile:
        return self.engine.evaluate(**kwargs)

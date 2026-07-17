from __future__ import annotations

from .pretrade_risk_engine import PreTradeRiskEngine
from .pretrade_risk_policy import PreTradeRiskPolicy
from .pretrade_risk_profile import (
    PreTradeAccountProfile,
    PreTradeRiskDecision,
    PreTradeRiskRequest,
)


class PreTradeRiskService:
    def __init__(self, policy: PreTradeRiskPolicy | None = None) -> None:
        self.engine = PreTradeRiskEngine(policy)

    def evaluate(
        self,
        request: PreTradeRiskRequest,
        account: PreTradeAccountProfile | None,
    ) -> PreTradeRiskDecision:
        return self.engine.evaluate(request, account)

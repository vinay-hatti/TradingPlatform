from __future__ import annotations
from .portfolio_risk_engine import PortfolioRiskEngine
from .portfolio_risk_policy import PortfolioRiskPolicy
from .portfolio_risk_profile import PortfolioRiskDecision, PortfolioSnapshotProfile
from .pretrade_risk_profile import PreTradeRiskRequest

class PortfolioRiskService:
    def __init__(self, policy: PortfolioRiskPolicy | None = None) -> None:
        self.engine = PortfolioRiskEngine(policy)

    def evaluate(self, order: PreTradeRiskRequest, snapshot: PortfolioSnapshotProfile) -> PortfolioRiskDecision:
        return self.engine.evaluate(order, snapshot)

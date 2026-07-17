from __future__ import annotations

from datetime import datetime

from .portfolio_greeks_policy import PortfolioGreeksMonitoringPolicy
from .portfolio_greeks_profile import (
    PortfolioGreeksDecision,
    RealTimePositionGreeks,
)
from .portfolio_greeks_repository import JsonPortfolioGreeksRepository
from .scenario_risk_monitoring_engine import ScenarioRiskMonitoringEngine


class PortfolioGreeksMonitoringService:
    def __init__(
        self,
        *,
        policy: PortfolioGreeksMonitoringPolicy | None = None,
        repository: JsonPortfolioGreeksRepository | None = None,
    ) -> None:
        self.policy = policy or PortfolioGreeksMonitoringPolicy()
        self.engine = ScenarioRiskMonitoringEngine(self.policy)
        self.repository = repository or JsonPortfolioGreeksRepository()

    def evaluate_and_publish(
        self,
        *,
        account_id: str,
        snapshot_id: str | None,
        current_equity: float,
        option_position_ids: tuple[str, ...],
        greeks: tuple[RealTimePositionGreeks, ...],
        as_of: datetime | None = None,
    ) -> PortfolioGreeksDecision:
        decision = self.engine.evaluate(
            account_id=account_id,
            snapshot_id=snapshot_id,
            current_equity=current_equity,
            option_position_ids=option_position_ids,
            greeks=greeks,
            as_of=as_of,
        )
        if decision.allowed and decision.risk_state is not None:
            self.repository.save(decision.risk_state)
        return decision

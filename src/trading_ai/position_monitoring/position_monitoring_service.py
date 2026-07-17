from __future__ import annotations

from datetime import datetime

from .intraday_risk_engine import IntradayRiskStateEngine
from .position_monitoring_policy import PositionMonitoringPolicy
from .position_monitoring_profile import (
    PositionSnapshotDecision,
    RealTimePositionSnapshot,
    RealTimeQuoteSnapshot,
)
from .position_snapshot_repository import JsonPositionSnapshotRepository


class PositionMonitoringService:
    def __init__(
        self,
        *,
        policy: PositionMonitoringPolicy | None = None,
        repository: JsonPositionSnapshotRepository | None = None,
    ) -> None:
        self.policy = policy or PositionMonitoringPolicy()
        self.engine = IntradayRiskStateEngine(self.policy)
        self.repository = (
            repository or JsonPositionSnapshotRepository()
        )

    def evaluate_and_publish(
        self,
        *,
        account_id: str,
        starting_equity: float,
        peak_equity: float,
        cash_balance: float,
        positions: tuple[RealTimePositionSnapshot, ...],
        quotes: dict[str, RealTimeQuoteSnapshot],
        as_of: datetime | None = None,
        snapshot_id: str | None = None,
    ) -> PositionSnapshotDecision:
        decision = self.engine.evaluate(
            account_id=account_id,
            starting_equity=starting_equity,
            peak_equity=peak_equity,
            cash_balance=cash_balance,
            positions=positions,
            quotes=quotes,
            as_of=as_of,
            snapshot_id=snapshot_id,
        )
        if (
            decision.allowed
            and decision.risk_state is not None
            and self.policy.persist_snapshots
        ):
            self.repository.save(decision.risk_state)
        return decision

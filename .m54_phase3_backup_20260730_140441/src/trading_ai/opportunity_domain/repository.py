from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import OpportunityAuditEventModel, OpportunityModel


class OpportunityRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, model: OpportunityModel) -> None:
        self.session.add(model)

    def add_event(self, event: OpportunityAuditEventModel) -> None:
        self.session.add(event)

    def get(self, opportunity_id: str) -> OpportunityModel | None:
        return self.session.get(OpportunityModel, opportunity_id)

    def find_by_source(self, scanner_run_id: str, snapshot_id: str, symbol: str, strategy: str) -> OpportunityModel | None:
        stmt = select(OpportunityModel).where(
            OpportunityModel.scanner_run_id == scanner_run_id,
            OpportunityModel.snapshot_id == snapshot_id,
            OpportunityModel.symbol == symbol,
            OpportunityModel.strategy == strategy,
        )
        return self.session.scalar(stmt)

    def list(self, *, state: str | None = None, limit: int = 100) -> list[OpportunityModel]:
        stmt = select(OpportunityModel)
        if state:
            stmt = stmt.where(OpportunityModel.workflow_state == state)
        stmt = stmt.order_by(OpportunityModel.created_at.desc()).limit(max(1, min(limit, 500)))
        return list(self.session.scalars(stmt))

    def events(self, opportunity_id: str) -> list[OpportunityAuditEventModel]:
        stmt = select(OpportunityAuditEventModel).where(
            OpportunityAuditEventModel.opportunity_id == opportunity_id
        ).order_by(OpportunityAuditEventModel.opportunity_version)
        return list(self.session.scalars(stmt))

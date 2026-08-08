from __future__ import annotations

from sqlalchemy import func, select

from trading_ai.broker_portfolio_sync.models import BrokerCurrentPositionModel, BrokerPortfolioPublicationModel
from trading_ai.database.session import SessionLocal
from trading_ai.portfolio_intelligence.models import ManagedPositionModel, PortfolioSnapshotModel
from trading_ai.portfolio_management.database_models import PortfolioPositionModel


def main() -> None:
    with SessionLocal() as session:
        broker = session.scalar(select(func.count()).select_from(BrokerCurrentPositionModel).where(BrokerCurrentPositionModel.active.is_(True))) or 0
        portfolio = session.scalar(select(func.count()).select_from(PortfolioPositionModel).where(PortfolioPositionModel.portfolio_id == "PAPER-PRIMARY", PortfolioPositionModel.status == "OPEN")) or 0
        managed = session.scalar(select(func.count()).select_from(ManagedPositionModel).where(ManagedPositionModel.portfolio_id == "PAPER-PRIMARY", ManagedPositionModel.state.notin_(["CLOSED", "CANCELLED"]))) or 0
        publication = session.scalar(select(BrokerPortfolioPublicationModel).where(BrokerPortfolioPublicationModel.portfolio_id == "PAPER-PRIMARY").order_by(BrokerPortfolioPublicationModel.published_at.desc()).limit(1))
        snapshot = session.scalar(select(PortfolioSnapshotModel).where(PortfolioSnapshotModel.portfolio_id == "PAPER-PRIMARY").order_by(PortfolioSnapshotModel.snapshot_timestamp.desc()).limit(1))
        print(f"Active broker positions: {broker}")
        print(f"Open portfolio positions: {portfolio}")
        print(f"Active managed positions: {managed}")
        print(f"Current broker publication: {publication.publication_id if publication else 'MISSING'}")
        print(f"Current portfolio snapshot: {snapshot.snapshot_id if snapshot else 'MISSING'}")
        ok = publication is not None and snapshot is not None and broker == portfolio and managed >= broker
        print(f"Milestone 63 operational acceptance: {'PASSED' if ok else 'FAILED'}")
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()

from sqlalchemy import Column, String, Float, Date
from trading_ai.database.base import Base


class PriceHistory(Base):
    __tablename__ = "price_history"
    symbol = Column(String(16), primary_key=True)
    date = Column(Date, primary_key=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)


# Import Milestone 36 portfolio models so Alembic sees their metadata.
from trading_ai.portfolio_management.database_models import (  # noqa: E402,F401
    PortfolioAccountModel,
    PortfolioAuditModel,
    PortfolioCashLedgerModel,
    PortfolioPositionModel,
    PortfolioSnapshotModel,
    PortfolioSyncRunModel,
)

# Import Milestone 38 execution orchestration models for Alembic metadata.
from trading_ai.execution_orchestration.database_models import (  # noqa: E402,F401
    ExecutionEventModel,
    ExecutionOrderModel,
    ExecutionRunModel,
)

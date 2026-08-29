from pathlib import Path
from tempfile import TemporaryDirectory
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from trading_ai.database.base import Base
from trading_ai.portfolio_risk_management.database_models import PortfolioRiskAssessmentModel
from trading_ai.portfolio_risk_management.database_service import PortfolioRiskDatabaseService
from trading_ai.portfolio_risk_management.serialization import write_json_atomic
from trading_ai.portfolio_risk_management.service import PortfolioRiskManagementService

engine = create_engine("sqlite+pysqlite:///:memory:")
Base.metadata.create_all(engine)
with TemporaryDirectory() as tmp:
    registry = Path(tmp) / "registry.json"
    write_json_atomic(registry, {"account": {"portfolio_id": "PRIMARY"}, "net_liquidation_value": 100000.0, "cash_balance": 100000.0, "positions": []})
    assessment = PortfolioRiskManagementService().assess(registry)
    with Session(engine) as session:
        service = PortfolioRiskDatabaseService()
        service.synchronize(session, assessment)
        service.synchronize(session, assessment)
        assert len(session.scalars(select(PortfolioRiskAssessmentModel)).all()) == 1
print("Milestone 37 database synchronization assertions passed.")

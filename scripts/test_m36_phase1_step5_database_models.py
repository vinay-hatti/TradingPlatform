from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from trading_ai.database.base import Base
from trading_ai.portfolio_management import database_models  # noqa: F401
from trading_ai.database.repositories.portfolio_management import PortfolioManagementRepository

engine = create_engine("sqlite+pysqlite:///:memory:")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
with Session() as session:
    repo = PortfolioManagementRepository(session)
    repo.upsert_account({"portfolio_id":"PRIMARY","name":"Test","base_currency":"USD","initial_capital":100000.0,"created_at":"2026-07-21T00:00:00+00:00","status":"ACTIVE","metadata":{}})
    session.commit()
    assert repo.counts("PRIMARY")["accounts"] == 1
print("Milestone 36 Phase 1 Step 5 database-model assertions passed.")

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from trading_ai.database.base import Base
from trading_ai.portfolio_management import database_models  # noqa: F401
from trading_ai.portfolio_management.database_service import PortfolioDatabaseSyncService

with TemporaryDirectory() as tmp:
    root = Path(tmp); snapshots = root / "snapshots"; snapshots.mkdir()
    registry = {"account":{"portfolio_id":"PRIMARY","name":"Test","base_currency":"USD","initial_capital":100000.0,"created_at":"2026-07-21T00:00:00+00:00","status":"ACTIVE","metadata":{}},"positions":[],"cash_ledger":[],"cash_balance":100000.0,"net_liquidation_value":100000.0,"total_capital_committed":0.0,"total_realized_pnl":0.0,"total_unrealized_pnl":0.0,"open_position_count":0,"closed_position_count":0}
    registry_file=root/"registry.json"; registry_file.write_text(json.dumps(registry))
    audit_file=root/"audit.json"; audit_file.write_text(json.dumps({"portfolio_id":"PRIMARY","records":[]}))
    engine=create_engine("sqlite+pysqlite:///:memory:"); Base.metadata.create_all(engine); Session=sessionmaker(bind=engine)
    service=PortfolioDatabaseSyncService(session_factory=Session)
    first=service.synchronize(registry_file=registry_file,snapshot_directory=snapshots,audit_file=audit_file)
    second=service.synchronize(registry_file=registry_file,snapshot_directory=snapshots,audit_file=audit_file)
    assert first["database_counts"]["accounts"] == 1
    assert second["database_counts"]["accounts"] == 1
    assert second["database_counts"]["sync_runs"] == 2
print("Milestone 36 Phase 1 Step 5 database-sync assertions passed.")

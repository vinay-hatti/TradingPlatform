from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trading_ai.database.base import Base
from trading_ai.institutional_options.models import InstitutionalOpportunityModel
from trading_ai.institutional_options.publication_scope import (
    latest_opportunity_ids,
    latest_stock_scanner_run_id,
)
from trading_ai.stock_intelligence.models import StockScannerPublicationModel


def _publication(identifier: str, run_id: str, timestamp: str):
    return StockScannerPublicationModel(
        id=identifier,
        symbol="__PUBLICATION__",
        scanner_run_id=run_id,
        candidate_id=None,
        snapshot_timestamp=timestamp,
        payload_json={},
        publication_name="current_stock_intelligence",
        status="READY",
    )


def _opportunity(identifier: str, symbol: str, run_id: str):
    return InstitutionalOpportunityModel(
        opportunity_id=identifier,
        symbol=symbol,
        asset_class="EQUITY",
        state="VALIDATED",
        direction="BULLISH",
        category="BULLISH",
        overall_score=80,
        confidence=80,
        conviction="HIGH",
        thesis_id=f"thesis-{identifier}",
        stock_publication_name="current_stock_intelligence",
        stock_scanner_run_id=run_id,
        stock_candidate_id=f"candidate-{identifier}",
        stock_state_hash=f"hash-{identifier}",
        option_snapshot_id=None,
        version=1,
        created_at="2026-08-04T00:00:00+00:00",
        updated_at="2026-08-04T00:00:00+00:00",
        payload_json={"opportunity_id": identifier, "symbol": symbol},
    )


def test_latest_publication_scope_returns_only_current_run_opportunities():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        session.add_all([
            _publication("pub-old", "run-old", "2026-08-03T00:00:00+00:00"),
            _publication("pub-new", "run-new", "2026-08-04T00:00:00+00:00"),
            _opportunity("opp-old-aapl", "AAPL", "run-old"),
            _opportunity("opp-new-aapl", "AAPL", "run-new"),
            _opportunity("opp-new-msft", "MSFT", "run-new"),
        ])
        session.commit()
        assert latest_stock_scanner_run_id(session) == "run-new"
        run_id, opportunity_ids = latest_opportunity_ids(session)
        assert run_id == "run-new"
        assert opportunity_ids == ["opp-new-aapl", "opp-new-msft"]


def test_router_and_options_orchestration_default_to_latest_publication():
    root = Path(__file__).resolve().parents[2]
    router = (root / "src/trading_ai/institutional_options/router.py").read_text()
    common = (root / "scripts/ingestion_split_common.py").read_text()
    page = (root / "ui/workstation/src/InstitutionalOptionsPage.tsx").read_text()
    assert 'view: str = Query("current"' in router
    assert "stock_scanner_run_id == latest_run_id" in router
    assert "latest_opportunity_ids(scope_session)" in common
    assert "opportunity_ids=scoped_opportunity_ids" in common
    assert '<option value="current">Current run</option>' in page
    assert '<option value="history">Historical</option>' in page

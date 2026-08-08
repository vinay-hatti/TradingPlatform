from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from trading_ai.database.base import Base
from trading_ai.institutional_options.models import InstitutionalOpportunityModel
from trading_ai.institutional_options.publication_scope import (
    latest_opportunity_ids,
    latest_published_stock_scanner_run_id,
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


def _opportunity(identifier: str, run_id: str):
    return InstitutionalOpportunityModel(
        opportunity_id=identifier,
        symbol="AAPL",
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
        payload_json={"opportunity_id": identifier, "symbol": "AAPL"},
    )


def test_newer_unmaterialized_options_publication_does_not_hide_underlying_run():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        session.add_all([
            _publication("pub-underlying", "run-underlying", "2026-08-05T01:06:22+00:00"),
            _opportunity("opp-aapl", "run-underlying"),
            _publication("pub-options", "run-options", "2026-08-05T01:19:52+00:00"),
        ])
        session.commit()
        assert latest_published_stock_scanner_run_id(session) == "run-options"
        assert latest_stock_scanner_run_id(session) == "run-underlying"
        run_id, opportunity_ids = latest_opportunity_ids(session)
        assert run_id == "run-underlying"
        assert opportunity_ids == ["opp-aapl"]


def test_new_materialized_run_becomes_current_immediately():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        session.add_all([
            _publication("pub-old", "run-old", "2026-08-04T01:00:00+00:00"),
            _opportunity("opp-old", "run-old"),
            _publication("pub-new", "run-new", "2026-08-05T01:00:00+00:00"),
            _opportunity("opp-new", "run-new"),
        ])
        session.commit()
        assert latest_stock_scanner_run_id(session) == "run-new"
        assert latest_opportunity_ids(session) == ("run-new", ["opp-new"])

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trading_ai.database.base import Base
from trading_ai.institutional_options.domain import OpportunityState, ThesisDirection
from trading_ai.institutional_options.models import (
    InstitutionalOpportunityAuditModel,
    InstitutionalOpportunityModel,
    OpportunityThesisModel,
)
from trading_ai.institutional_options.opportunity_ingestion import (
    InstitutionalOpportunityIngestionService,
    OpportunityEligibilityPolicy,
    StockOpportunityEligibilityService,
)
from trading_ai.stock_intelligence.models import (
    StockScannerCandidateModel,
    StockScannerPublicationModel,
)


def payload(*, score=88, confidence=82, freshness=95, direction="BULLISH", state_hash="hash-1", stop=186, targets=(198, 204)):
    return {
        "provider": "polygon",
        "direction": direction,
        "structure": "TRENDING",
        "primary_timeframe": "1d",
        "alignment_score": 85,
        "state_hash": state_hash,
        "scores": {
            "overall": score,
            "confidence": confidence,
            "freshness": freshness,
            "primary_category": "TREND_CONTINUATION",
        },
        "timeframe_states": {"1d": {"direction": "STRONG_BULLISH", "structure": "TRENDING"}},
        "participation": {"state": "ACCUMULATION"},
        "breakout": {"state": "BREAKOUT_RETEST"},
        "context": {
            "market_regime": "UPTREND",
            "forecast_direction": "BULLISH",
            "relative_strength_grade": "A",
            "dealer_positioning": "POSITIVE_GAMMA",
            "gamma_regime": "POSITIVE",
        },
        "trade_plan": {
            "entry": {"zone_low": 190, "zone_high": 191, "rationale": ["Primary support retest"]},
            "stop": {"recommended_stop": stop},
            "targets": {"targets": [{"price": x} for x in targets]},
            "management_quality": 90,
            "structural_reward_risk": 2.5,
            "expected_hold_days": 10,
        },
        "metadata": {"asset_class": "EQUITY"},
        "warnings": [],
    }


def seed(session: Session, candidates: list[dict]):
    timestamp = datetime.now(timezone.utc).isoformat()
    session.add(StockScannerPublicationModel(
        id="publication-1", symbol="*", scanner_run_id="stock-run-1", candidate_id=None,
        snapshot_timestamp=timestamp, publication_name="current_stock_intelligence", status="READY",
        payload_json={"market_publication_name": "current_market_state", "market_run_id": "market-run-1"},
    ))
    for index, item in enumerate(candidates, 1):
        session.add(StockScannerCandidateModel(
            id=f"candidate-{index}", symbol=item.pop("symbol", f"SYM{index}"), scanner_run_id="stock-run-1",
            candidate_id=f"candidate-{index}", snapshot_timestamp=timestamp,
            category=(item.get("scores") or {}).get("primary_category", "UNKNOWN"),
            score=(item.get("scores") or {}).get("overall", 0), payload_json=item,
        ))
    session.flush()


def test_eligibility_accepts_complete_fresh_candidate():
    decision = StockOpportunityEligibilityService().evaluate(payload(), snapshot_timestamp=datetime.now(timezone.utc).isoformat())
    assert decision.eligible
    assert decision.opportunity_quality > 70


def test_eligibility_rejects_low_score():
    decision = StockOpportunityEligibilityService().evaluate(payload(score=40), snapshot_timestamp=datetime.now(timezone.utc).isoformat())
    assert not decision.eligible
    assert "UNDERLYING_SCORE_BELOW_MINIMUM" in decision.reasons


def test_eligibility_rejects_neutral_direction():
    decision = StockOpportunityEligibilityService().evaluate(payload(direction="NEUTRAL"), snapshot_timestamp=datetime.now(timezone.utc).isoformat())
    assert "NEUTRAL_DIRECTION" in decision.reasons


def test_eligibility_rejects_missing_structural_management():
    value = payload(stop=0, targets=())
    decision = StockOpportunityEligibilityService().evaluate(value, snapshot_timestamp=datetime.now(timezone.utc).isoformat())
    assert "STRUCTURAL_STOP_MISSING" in decision.reasons
    assert "DYNAMIC_TARGETS_MISSING" in decision.reasons


def test_eligibility_rejects_missing_state_hash():
    decision = StockOpportunityEligibilityService().evaluate(payload(state_hash=""), snapshot_timestamp=datetime.now(timezone.utc).isoformat())
    assert "STATE_HASH_MISSING" in decision.reasons


def test_ingestion_persists_and_validates_opportunity():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session, [{"symbol": "AAPL", **payload()}])
        result = InstitutionalOpportunityIngestionService(session).ingest()
        session.commit()
        assert result.validated == 1
        row = session.query(InstitutionalOpportunityModel).one()
        assert row.state == OpportunityState.VALIDATED.value
        assert row.symbol == "AAPL"
        assert session.query(OpportunityThesisModel).count() == 1
        assert session.query(InstitutionalOpportunityAuditModel).count() == 1


def test_ingestion_preserves_stock_and_market_lineage():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session, [{"symbol": "MSFT", **payload()}])
        InstitutionalOpportunityIngestionService(session).ingest()
        row = session.query(InstitutionalOpportunityModel).one()
        assert row.stock_publication_name == "current_stock_intelligence"
        assert row.stock_scanner_run_id == "stock-run-1"
        assert row.stock_state_hash == "hash-1"
        assert row.payload_json["lineage"]["market_run_id"] == "market-run-1"


def test_ingestion_isolates_rejected_candidates():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session, [{"symbol": "GOOD", **payload()}, {"symbol": "BAD", **payload(score=20)}])
        result = InstitutionalOpportunityIngestionService(session).ingest()
        assert result.validated == 1
        assert result.rejected == 1
        assert result.rejection_counts["UNDERLYING_SCORE_BELOW_MINIMUM"] == 1


def test_ingestion_symbol_filter_limits_scope():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session, [{"symbol": "AAPL", **payload()}, {"symbol": "MSFT", **payload()}])
        result = InstitutionalOpportunityIngestionService(session).ingest(symbols=["MSFT"])
        assert result.requested == 1
        assert session.query(InstitutionalOpportunityModel).one().symbol == "MSFT"


def test_thesis_direction_and_dynamic_levels_are_adapted():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session, [{"symbol": "AAPL", **payload()}])
        InstitutionalOpportunityIngestionService(session).ingest()
        thesis = session.query(OpportunityThesisModel).one().payload_json
        assert thesis["direction"] == ThesisDirection.BULLISH.value
        assert thesis["entry_zone_low"] == 190
        assert thesis["invalidation_level"] == 186
        assert thesis["targets"] == [198.0, 204.0]


def test_api_routes_are_registered_without_changing_existing_scanners():
    from pathlib import Path
    app_source = Path("src/trading_ai/production_api/app.py").read_text()
    router_source = Path("src/trading_ai/institutional_options/router.py").read_text()
    assert "institutional_options_router" in app_source
    assert "app.include_router(institutional_options_router)" in app_source
    assert "@router.get(\"/opportunities\"" in router_source
    assert "@router.post(\"/opportunities/ingest\"" in router_source
    assert Path("src/trading_ai/stock_intelligence/router.py").exists()


def test_eligibility_rejects_unambiguous_category_direction_conflict():
    value = payload(direction="BULLISH")
    value["scores"]["primary_category"] = "BREAKDOWN"
    decision = StockOpportunityEligibilityService().evaluate(
        value,
        snapshot_timestamp=datetime.now(timezone.utc).isoformat(),
    )
    assert not decision.eligible
    assert "CATEGORY_DIRECTION_CONFLICT" in decision.reasons


def test_eligibility_allows_failed_breakdown_bullish_reversal():
    value = payload(direction="BULLISH")
    value["scores"]["primary_category"] = "FAILED_BREAKDOWN_RECLAIM"
    decision = StockOpportunityEligibilityService().evaluate(
        value,
        snapshot_timestamp=datetime.now(timezone.utc).isoformat(),
    )
    assert decision.eligible


def test_ingestion_reads_nested_market_and_option_lineage():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session, [{"symbol": "AAPL", **payload()}])
        publication = session.get(StockScannerPublicationModel, "publication-1")
        publication.payload_json = {
            "lineage": {
                "market_publication_name": "current_market_state",
                "market_publication_run_id": "market-run-nested",
                "option_snapshot_id": "options-run-nested",
                "option_snapshot_timestamp": "2026-08-04T17:47:01+00:00",
            }
        }
        InstitutionalOpportunityIngestionService(session).ingest()
        row = session.query(InstitutionalOpportunityModel).one()
        lineage = row.payload_json["lineage"]
        assert lineage["market_run_id"] == "market-run-nested"
        assert lineage["option_snapshot_id"] == "options-run-nested"
        assert lineage["option_snapshot_timestamp"] == "2026-08-04T17:47:01+00:00"
        assert row.option_snapshot_id == "options-run-nested"


def test_repeat_ingestion_is_idempotent_and_refreshes_lineage_without_duplicate_audit():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session, [{"symbol": "AAPL", **payload()}])
        service = InstitutionalOpportunityIngestionService(session)
        first = service.ingest()
        session.flush()
        first_id = first.opportunity_ids[0]
        assert session.query(InstitutionalOpportunityAuditModel).count() == 1

        publication = session.get(StockScannerPublicationModel, "publication-1")
        publication.payload_json = {
            "lineage": {
                "market_publication_run_id": "market-run-refreshed",
                "option_snapshot_id": "options-run-refreshed",
                "option_snapshot_timestamp": "2026-08-04T18:00:00+00:00",
            }
        }
        second = service.ingest()
        session.flush()

        assert second.discovered == 0
        assert second.validated == 1
        assert second.existing == 1
        assert second.refreshed == 1
        assert second.opportunity_ids == (first_id,)
        assert session.query(InstitutionalOpportunityModel).count() == 1
        assert session.query(OpportunityThesisModel).count() == 1
        assert session.query(InstitutionalOpportunityAuditModel).count() == 1
        row = session.get(InstitutionalOpportunityModel, first_id)
        assert row.payload_json["lineage"]["market_run_id"] == "market-run-refreshed"
        assert row.option_snapshot_id == "options-run-refreshed"


def test_repeat_ingestion_rejects_existing_candidate_after_category_direction_conflict():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session, [{"symbol": "AAPL", **payload()}])
        service = InstitutionalOpportunityIngestionService(session)
        first = service.ingest()
        candidate = session.get(StockScannerCandidateModel, "candidate-1")
        changed = dict(candidate.payload_json)
        changed["scores"] = {**changed["scores"], "primary_category": "BREAKDOWN"}
        candidate.payload_json = changed
        candidate.category = "BREAKDOWN"
        session.flush()

        second = service.ingest()
        row = session.get(InstitutionalOpportunityModel, first.opportunity_ids[0])
        assert second.existing_rejected == 1
        assert second.rejection_counts["CATEGORY_DIRECTION_CONFLICT"] == 1
        assert row.state == OpportunityState.REJECTED.value
        assert session.query(InstitutionalOpportunityAuditModel).count() == 2

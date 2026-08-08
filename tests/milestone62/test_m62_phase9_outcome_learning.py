from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trading_ai.database.base import Base
from trading_ai.institutional_options.models import (
    InstitutionalOpportunityModel, OpportunityThesisModel,
    StrategyCandidateModel, StrategyValuationModel,
    InstitutionalOptionOutcomeObservationModel,
    InstitutionalOptionLearningSnapshotModel,
)
from trading_ai.institutional_options.outcome_learning import (
    InstitutionalOptionsOutcomeLearningService, OutcomeObservationInput,
)


def seeded_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(InstitutionalOpportunityModel(
        opportunity_id="opp-1", symbol="AAPL", asset_class="EQUITY", state="CLOSED",
        direction="BULLISH", category="BREAKOUT", overall_score=90, confidence=88,
        conviction="HIGH", thesis_id="thesis-1", stock_publication_name="current_stock_intelligence",
        stock_scanner_run_id="run-1", stock_candidate_id="candidate-1", stock_state_hash="hash-1",
        option_snapshot_id="snap-1", version=1, created_at="2026-08-01T00:00:00+00:00",
        updated_at="2026-08-04T00:00:00+00:00", payload_json={}
    ))
    session.add(OpportunityThesisModel(
        thesis_id="thesis-1", opportunity_id="opp-1", direction="BULLISH", setup_category="BREAKOUT",
        primary_timeframe="1d", invalidation_level=190, entry_zone_low=198, entry_zone_high=200,
        created_at="2026-08-01T00:00:00+00:00", payload_json={"market_regime":"UPTREND"}
    ))
    session.add(StrategyCandidateModel(
        strategy_candidate_id="strategy-1", opportunity_id="opp-1", strategy="BULL_CALL_SPREAD",
        disposition="SELECTED", eligibility_score=91, strategy_score=94, complexity="LOW", rank=1,
        selected=True, payload_json={}
    ))
    session.add(StrategyValuationModel(
        valuation_id="valuation-1", opportunity_id="opp-1", strategy_candidate_id="strategy-1",
        strategy_score=94, calibrated_probability=.72, expected_value=300, expected_return_on_risk=.4,
        selected=True, created_at="2026-08-01T00:00:00+00:00", payload_json={}
    ))
    session.commit()
    return session


def test_capture_persists_immutable_attribution():
    with seeded_session() as session:
        service = InstitutionalOptionsOutcomeLearningService(session)
        result = service.capture(OutcomeObservationInput(
            opportunity_id="opp-1", entry_timestamp="2026-08-01T14:30:00+00:00",
            exit_timestamp="2026-08-04T18:00:00+00:00", underlying_entry=200,
            underlying_exit=208, option_entry_value=3.0, option_exit_value=4.5,
            quantity=2, exit_reason="TARGET_ZONE_REACHED", mfe_pct=60, mae_pct=-12,
        ))
        assert result.outcome == "WIN"
        assert round(result.realized_return_pct, 2) == 50.0
        assert session.query(InstitutionalOptionOutcomeObservationModel).count() == 1
        try:
            service.capture(OutcomeObservationInput(
                opportunity_id="opp-1", entry_timestamp="x", exit_timestamp="y",
                underlying_entry=1, underlying_exit=2, option_entry_value=1,
                option_exit_value=2, quantity=1, exit_reason="X",
            ))
        except ValueError as exc:
            assert "immutable" in str(exc)
        else:
            raise AssertionError("Expected immutable duplicate rejection")


def test_learning_summary_calculates_probability_metrics_and_warnings():
    with seeded_session() as session:
        service = InstitutionalOptionsOutcomeLearningService(session)
        service.capture(OutcomeObservationInput(
            opportunity_id="opp-1", entry_timestamp="2026-08-01", exit_timestamp="2026-08-04",
            underlying_entry=200, underlying_exit=208, option_entry_value=3.0,
            option_exit_value=4.5, quantity=1, exit_reason="TARGET", mfe_pct=60, mae_pct=-12,
        ))
        summary = service.summarize()
        assert summary.observation_count == 1
        assert summary.win_rate == 1.0
        assert summary.brier_score is not None
        assert "SMALL_SAMPLE_SIZE" in summary.warnings
        assert session.query(InstitutionalOptionLearningSnapshotModel).count() == 1


def test_outcome_routes_registered():
    from pathlib import Path
    router = Path("src/trading_ai/institutional_options/router.py").read_text()
    assert "/outcomes/capture" in router
    assert "/learning/summarize" in router

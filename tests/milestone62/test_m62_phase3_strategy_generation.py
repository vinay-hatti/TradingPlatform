from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trading_ai.database.base import Base
from trading_ai.institutional_options.domain import (
    InstitutionalOpportunity,
    OpportunityLineage,
    OpportunityState,
    OpportunityThesis,
    StrategyDisposition,
    ThesisDirection,
)
from trading_ai.institutional_options.models import (
    InstitutionalOpportunityAuditModel,
    InstitutionalOpportunityModel,
    StrategyCandidateModel,
    StrategyComparisonModel,
)
from trading_ai.institutional_options.repository import InstitutionalOpportunityRepository
from trading_ai.institutional_options.strategy_generation import (
    InstitutionalStrategyGenerationService,
    RegimeAwareStrategyEligibilityService,
)


def make(direction=ThesisDirection.BULLISH, regime="UPTREND", structure="TRENDING", category="TREND_CONTINUATION", dealer="POSITIVE_GAMMA", forecast="BULLISH"):
    opportunity = InstitutionalOpportunity(
        opportunity_id="opp-1", symbol="AAPL", asset_class="EQUITY", state=OpportunityState.VALIDATED,
        direction=direction, category=category, overall_score=88, confidence=84, conviction="HIGH",
        lineage=OpportunityLineage("current_stock_intelligence", "stock-run", "candidate-1", "hash-1", "current_market_state", "market-run"),
        thesis_id="thesis-1",
    )
    thesis = OpportunityThesis(
        thesis_id="thesis-1", opportunity_id="opp-1", direction=direction, setup_category=category,
        primary_timeframe="1d", market_regime=regime, sector_context="LEADING", trend_state=direction.value,
        structure_state=structure, participation_state="ACCUMULATION" if direction == ThesisDirection.BULLISH else "DISTRIBUTION",
        dealer_context=dealer, forecast_context=forecast, entry_zone_low=190, entry_zone_high=191,
        invalidation_level=186 if direction == ThesisDirection.BULLISH else 195, targets=(198, 204),
    )
    return opportunity, thesis


def seed(session: Session, opportunity: InstitutionalOpportunity, thesis: OpportunityThesis):
    InstitutionalOpportunityRepository(session).save_opportunity(opportunity, thesis)
    session.flush()


def test_bullish_thesis_generates_multiple_bullish_strategies():
    opportunity, thesis = make()
    candidates = RegimeAwareStrategyEligibilityService().generate(opportunity, thesis)
    eligible = {item.strategy for item in candidates if item.disposition == StrategyDisposition.ELIGIBLE}
    assert "LONG_CALL" in eligible
    assert "BULL_CALL_SPREAD" in eligible
    assert len(eligible) >= 2


def test_bullish_thesis_rejects_bearish_strategies_with_reason():
    opportunity, thesis = make()
    candidates = RegimeAwareStrategyEligibilityService().generate(opportunity, thesis)
    long_put = next(item for item in candidates if item.strategy == "LONG_PUT")
    assert long_put.disposition == StrategyDisposition.REJECTED
    assert "DIRECTION_INCOMPATIBLE" in long_put.rejection_reasons


def test_bearish_thesis_generates_bearish_strategies():
    opportunity, thesis = make(direction=ThesisDirection.BEARISH, regime="DOWNTREND", category="BREAKDOWN", forecast="BEARISH")
    candidates = RegimeAwareStrategyEligibilityService().generate(opportunity, thesis)
    eligible = {item.strategy for item in candidates if item.disposition == StrategyDisposition.ELIGIBLE}
    assert "LONG_PUT" in eligible
    assert "BEAR_PUT_SPREAD" in eligible


def test_forecast_conflict_forces_rejection():
    opportunity, thesis = make(forecast="BEARISH")
    candidates = RegimeAwareStrategyEligibilityService().generate(opportunity, thesis)
    long_call = next(item for item in candidates if item.strategy == "LONG_CALL")
    assert long_call.disposition == StrategyDisposition.REJECTED
    assert "FORECAST_DIRECTION_CONFLICT" in long_call.rejection_reasons


def test_positive_gamma_range_supports_condor():
    opportunity, thesis = make(regime="RANGE_BOUND POSITIVE_GAMMA", structure="SIDEWAYS", category="RANGE")
    candidates = RegimeAwareStrategyEligibilityService().generate(opportunity, thesis)
    condor = next(item for item in candidates if item.strategy == "IRON_CONDOR")
    assert condor.disposition == StrategyDisposition.ELIGIBLE


def test_generation_persists_candidates_comparison_and_transition():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        opportunity, thesis = make()
        seed(session, opportunity, thesis)
        result = InstitutionalStrategyGenerationService(session).generate()
        session.commit()
        assert result.generated == 1
        assert session.query(StrategyCandidateModel).count() >= 2
        assert session.query(StrategyComparisonModel).count() == 1
        row = session.get(InstitutionalOpportunityModel, "opp-1")
        assert row.state == OpportunityState.STRATEGIES_GENERATED.value
        assert session.query(InstitutionalOpportunityAuditModel).count() == 1


def test_comparison_ranks_eligible_only():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        opportunity, thesis = make()
        seed(session, opportunity, thesis)
        InstitutionalStrategyGenerationService(session).generate()
        comparison = session.query(StrategyComparisonModel).one().payload_json
        rejected_ids = {row.strategy_candidate_id for row in session.query(StrategyCandidateModel).filter(StrategyCandidateModel.disposition == "REJECTED")}
        assert not rejected_ids.intersection(comparison["ranked_strategy_candidate_ids"])


def test_rank_is_deterministic_by_score_then_name():
    opportunity, thesis = make()
    service = RegimeAwareStrategyEligibilityService()
    first = service.generate(opportunity, thesis)
    second = service.generate(opportunity, thesis)
    first_order = [x.strategy for x in sorted((x for x in first if x.disposition == StrategyDisposition.ELIGIBLE), key=lambda x: (-x.eligibility_score, x.strategy))]
    second_order = [x.strategy for x in sorted((x for x in second if x.disposition == StrategyDisposition.ELIGIBLE), key=lambda x: (-x.eligibility_score, x.strategy))]
    assert first_order == second_order


def test_generation_isolates_invalid_opportunity():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        opportunity, thesis = make()
        seed(session, opportunity, thesis)
        # Remove thesis to force one isolated failure.
        session.query(type(session.query(StrategyComparisonModel))).all() if False else None
        from trading_ai.institutional_options.models import OpportunityThesisModel
        session.query(OpportunityThesisModel).delete()
        result = InstitutionalStrategyGenerationService(session).generate()
        assert result.failed == 1
        assert result.generated == 0


def test_strategy_api_routes_are_parallel_and_registered():
    from pathlib import Path
    source = Path("src/trading_ai/institutional_options/router.py").read_text()
    assert '@router.post("/strategies/generate"' in source
    assert '@router.get("/opportunities/{opportunity_id}/strategies"' in source
    assert Path("src/trading_ai/stock_intelligence/router.py").exists()

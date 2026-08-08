from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trading_ai.database.base import Base
from trading_ai.institutional_options.domain import (
    ContractLegRecommendation,
    ContractRecommendation,
    ContractSide,
    InstitutionalOpportunity,
    OpportunityLineage,
    OpportunityState,
    OpportunityThesis,
    StrategyCandidate,
    StrategyDisposition,
    ThesisDirection,
)
from trading_ai.institutional_options.models import (
    InstitutionalOpportunityModel,
    StrategyCandidateModel,
    StrategyComparisonModel,
)
from trading_ai.institutional_options.repository import InstitutionalOpportunityRepository
from trading_ai.institutional_options.valuation import (
    InstitutionalStrategyValuationService,
    StrategyValuationPolicy,
)


def _seed(session: Session, *, liquidity_score: float) -> str:
    opportunity_id = f"opp-{int(liquidity_score)}"
    lineage = OpportunityLineage(
        stock_publication_name="current_stock_intelligence",
        stock_scanner_run_id="run-1",
        stock_candidate_id=f"candidate-{opportunity_id}",
        stock_state_hash=f"hash-{opportunity_id}",
        option_snapshot_id="snapshot-1",
    )
    opportunity = InstitutionalOpportunity(
        opportunity_id=opportunity_id,
        symbol="TEST",
        asset_class="EQUITY",
        state=OpportunityState.CONTRACTS_OPTIMIZED,
        direction=ThesisDirection.BULLISH,
        category="TREND_CONTINUATION",
        overall_score=80.0,
        confidence=80.0,
        conviction="HIGH",
        lineage=lineage,
        thesis_id=f"thesis-{opportunity_id}",
    )
    thesis = OpportunityThesis(
        thesis_id=opportunity.thesis_id,
        opportunity_id=opportunity_id,
        direction=ThesisDirection.BULLISH,
        setup_category="TREND_CONTINUATION",
        primary_timeframe="1d",
        market_regime="BULLISH",
        sector_context="LEADING",
        trend_state="BULLISH",
        structure_state="TRENDING",
        participation_state="ACCUMULATION",
        dealer_context="BULLISH",
        forecast_context="BULLISH",
        entry_zone_low=100.0,
        entry_zone_high=101.0,
        invalidation_level=97.0,
        targets=(108.0,),
    )
    strategy = StrategyCandidate(
        strategy_candidate_id=f"strategy-{opportunity_id}",
        opportunity_id=opportunity_id,
        strategy="LONG_CALL",
        disposition=StrategyDisposition.ELIGIBLE,
        eligibility_score=80.0,
        complexity="LOW",
    )
    leg = ContractLegRecommendation(
        leg_id=f"leg-{opportunity_id}",
        side=ContractSide.BUY,
        option_type="CALL",
        option_symbol="O:TEST261218C00105000",
        expiry="2026-12-18",
        strike=105.0,
        bid=5.0,
        ask=5.2,
        delta=0.55,
        volume=100.0,
        open_interest=1000.0,
    )
    contract = ContractRecommendation(
        contract_recommendation_id=f"contract-{opportunity_id}",
        strategy_candidate_id=strategy.strategy_candidate_id,
        opportunity_id=opportunity_id,
        option_snapshot_id="snapshot-1",
        strategy="LONG_CALL",
        legs=(leg,),
        executable=True,
        liquidity_score=liquidity_score,
    )
    repo = InstitutionalOpportunityRepository(session)
    repo.save_opportunity(opportunity, thesis)
    repo.save_strategy_candidates([strategy])
    repo.save_contract_recommendation(contract)
    session.flush()
    return opportunity_id


def test_all_rejected_valuations_are_persisted_and_opportunity_is_governed_rejected():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        opportunity_id = _seed(session, liquidity_score=10.0)
        result = InstitutionalStrategyValuationService(session).value(
            opportunity_ids=(opportunity_id,), limit=None
        )
        session.commit()

        assert result.failed == 0
        assert result.selected == 0
        assert result.valued == 1
        assert result.rejected == 1
        row = session.get(InstitutionalOpportunityModel, opportunity_id)
        assert row.state == OpportunityState.REJECTED.value
        strategy = session.query(StrategyCandidateModel).filter_by(
            opportunity_id=opportunity_id
        ).one()
        assert strategy.disposition == StrategyDisposition.REJECTED.value
        assert "LIQUIDITY_BELOW_MINIMUM" in strategy.payload_json["rejection_reasons"]
        comparison = session.query(StrategyComparisonModel).filter_by(
            opportunity_id=opportunity_id
        ).one()
        assert comparison.selected_strategy_candidate_id is None


def test_eligible_valuation_still_advances_to_ready_for_execution():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        opportunity_id = _seed(session, liquidity_score=90.0)
        result = InstitutionalStrategyValuationService(
            session,
            StrategyValuationPolicy(minimum_probability=0.01),
        ).value(opportunity_ids=(opportunity_id,), limit=None)
        session.commit()

        assert result.failed == 0
        assert result.selected == 1
        row = session.get(InstitutionalOpportunityModel, opportunity_id)
        assert row.state == OpportunityState.READY_FOR_EXECUTION.value

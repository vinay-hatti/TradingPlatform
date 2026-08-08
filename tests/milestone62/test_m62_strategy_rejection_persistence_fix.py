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
    StrategyEligibilityPolicy,
)


def test_all_rejected_evaluations_persist_without_lifecycle_advance():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    opportunity = InstitutionalOpportunity(
        opportunity_id="opp-rejected-only",
        symbol="TEST",
        asset_class="EQUITY",
        state=OpportunityState.VALIDATED,
        direction=ThesisDirection.BULLISH,
        category="BULLISH",
        overall_score=75,
        confidence=80,
        conviction="HIGH",
        lineage=OpportunityLineage(
            "current_stock_intelligence", "stock-run", "candidate", "hash",
            "current_market_state", "market-run",
        ),
        thesis_id="thesis-rejected-only",
    )
    thesis = OpportunityThesis(
        thesis_id="thesis-rejected-only",
        opportunity_id="opp-rejected-only",
        direction=ThesisDirection.BULLISH,
        setup_category="BULLISH",
        primary_timeframe="1d",
        market_regime="UPTREND",
        sector_context=None,
        trend_state="BULLISH",
        structure_state="TRENDING",
        participation_state=None,
        dealer_context=None,
        forecast_context=None,
        entry_zone_low=100,
        entry_zone_high=101,
        invalidation_level=97,
        targets=(106,),
    )
    with Session(engine) as session:
        InstitutionalOpportunityRepository(session).save_opportunity(opportunity, thesis)
        session.flush()
        result = InstitutionalStrategyGenerationService(
            session,
            policy=StrategyEligibilityPolicy(minimum_eligibility_score=101),
        ).generate()
        session.commit()

        rows = session.query(StrategyCandidateModel).all()
        assert result.generated == 0
        assert result.failed == 1
        assert result.rejected_candidates == 12
        assert len(rows) == 12
        assert all(row.disposition == StrategyDisposition.REJECTED.value for row in rows)
        assert all((row.payload_json or {}).get("rejection_reasons") for row in rows)
        assert session.query(StrategyComparisonModel).count() == 0
        assert session.get(InstitutionalOpportunityModel, opportunity.opportunity_id).state == OpportunityState.VALIDATED.value
        assert session.query(InstitutionalOpportunityAuditModel).count() == 0

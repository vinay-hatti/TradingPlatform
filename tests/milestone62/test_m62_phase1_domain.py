from __future__ import annotations

import pytest
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
    ProbabilityDecomposition,
    StrategyCandidate,
    StrategyComparison,
    StrategyDisposition,
    ThesisDirection,
    deterministic_hash,
    serialize_domain,
)
from trading_ai.institutional_options.models import (
    InstitutionalOpportunityAuditModel,
    InstitutionalOpportunityModel,
)
from trading_ai.institutional_options.policy import OpportunityGovernancePolicy
from trading_ai.institutional_options.repository import InstitutionalOpportunityRepository


def sample():
    lineage = OpportunityLineage(
        stock_publication_name="current_stock_intelligence",
        stock_scanner_run_id="stock-scan-1",
        stock_candidate_id="candidate-AAPL",
        stock_state_hash="abc123",
        market_publication_name="current_market_state",
        market_run_id="market-1",
        option_snapshot_id="options-1",
    )
    thesis = OpportunityThesis(
        thesis_id="thesis-1",
        opportunity_id="opp-1",
        direction=ThesisDirection.BULLISH,
        setup_category="TREND_CONTINUATION",
        primary_timeframe="1d",
        market_regime="UPTREND",
        sector_context="LEADING",
        trend_state="STRONG_BULLISH",
        structure_state="TRENDING",
        participation_state="ACCUMULATION",
        dealer_context="POSITIVE_GAMMA",
        forecast_context="BULLISH",
        entry_zone_low=190,
        entry_zone_high=191,
        invalidation_level=186,
        targets=(198, 204),
        evidence=("weekly and daily trend aligned",),
    )
    opportunity = InstitutionalOpportunity(
        opportunity_id="opp-1",
        symbol="AAPL",
        asset_class="EQUITY",
        state=OpportunityState.DISCOVERED,
        direction=ThesisDirection.BULLISH,
        category="TREND_CONTINUATION",
        overall_score=88,
        confidence=82,
        conviction="HIGH",
        lineage=lineage,
        thesis_id="thesis-1",
    )
    return opportunity, thesis


def test_serialization_and_hash_are_deterministic():
    opportunity, thesis = sample()
    assert serialize_domain(opportunity)["state"] == "DISCOVERED"
    assert deterministic_hash(opportunity, thesis) == deterministic_hash(opportunity, thesis)


def test_policy_accepts_polygon_backed_opportunity():
    opportunity, thesis = sample()
    OpportunityGovernancePolicy().validate_opportunity(opportunity, thesis)


def test_policy_rejects_non_polygon_lineage():
    opportunity, thesis = sample()
    bad = InstitutionalOpportunity(**{**opportunity.__dict__, "lineage": OpportunityLineage(
        stock_publication_name="x", stock_scanner_run_id="x", stock_candidate_id="x", stock_state_hash="x", source_provider="OTHER"
    )})
    with pytest.raises(ValueError, match="Polygon"):
        OpportunityGovernancePolicy().validate_opportunity(bad, thesis)


def test_state_machine_blocks_skipped_transition():
    with pytest.raises(ValueError, match="Invalid"):
        OpportunityGovernancePolicy().validate_transition(OpportunityState.DISCOVERED, OpportunityState.CONTRACTS_OPTIMIZED)


def test_strategy_candidate_contracts_are_explicit():
    candidate = StrategyCandidate(
        strategy_candidate_id="strat-1", opportunity_id="opp-1", strategy="BULL_CALL_SPREAD",
        disposition=StrategyDisposition.ELIGIBLE, eligibility_score=90,
        probability=ProbabilityDecomposition(underlying_probability=.72),
    )
    assert serialize_domain(candidate)["strategy"] == "BULL_CALL_SPREAD"


def test_exact_contract_identity_is_required():
    recommendation = ContractRecommendation(
        contract_recommendation_id="contract-1", strategy_candidate_id="strat-1", opportunity_id="opp-1",
        option_snapshot_id="options-1", legs=(ContractLegRecommendation(
            leg_id="leg-1", side=ContractSide.BUY, option_type="CALL", option_symbol="", expiry="2026-09-18", strike=200,
        ),),
    )
    with pytest.raises(ValueError, match="option_symbol"):
        OpportunityGovernancePolicy().validate_contract_recommendation(recommendation)


def test_distinct_multi_leg_contracts_are_required():
    leg = ContractLegRecommendation(leg_id="1", side=ContractSide.BUY, option_type="CALL", option_symbol="O:AAPL1", expiry="2026-09-18", strike=200)
    recommendation = ContractRecommendation(
        contract_recommendation_id="contract-1", strategy_candidate_id="strat-1", opportunity_id="opp-1",
        option_snapshot_id="options-1", legs=(leg, ContractLegRecommendation(**{**leg.__dict__, "leg_id": "2", "side": ContractSide.SELL})),
    )
    with pytest.raises(ValueError, match="distinct"):
        OpportunityGovernancePolicy().validate_contract_recommendation(recommendation)


def test_metadata_registers_all_phase1_tables():
    required = {
        "institutional_option_opportunities", "institutional_option_theses", "institutional_option_strategy_candidates",
        "institutional_option_strategy_comparisons", "institutional_option_contract_recommendations",
        "institutional_option_execution_recommendations", "institutional_option_outcome_attributions",
        "institutional_option_opportunity_audit",
    }
    assert required.issubset(Base.metadata.tables)


def test_repository_persists_and_transitions():
    opportunity, thesis = sample()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        repo = InstitutionalOpportunityRepository(session)
        repo.save_opportunity(opportunity, thesis)
        repo.transition("opp-1", OpportunityState.VALIDATED, "test", "thesis passed")
        session.commit()
        row = session.get(InstitutionalOpportunityModel, "opp-1")
        assert row.state == "VALIDATED"
        assert row.version == 2
        assert session.query(InstitutionalOpportunityAuditModel).count() == 1


def test_strategy_comparison_preserves_ranked_alternatives():
    comparison = StrategyComparison(
        comparison_id="cmp-1", opportunity_id="opp-1",
        ranked_strategy_candidate_ids=("spread", "call", "diagonal"), selected_strategy_candidate_id="spread",
        comparison_policy_version="M62-PH1-1.0", rationale=("best risk-adjusted return",),
    )
    payload = serialize_domain(comparison)
    assert payload["ranked_strategy_candidate_ids"] == ["spread", "call", "diagonal"]

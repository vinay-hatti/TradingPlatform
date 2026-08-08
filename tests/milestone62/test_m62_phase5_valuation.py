from trading_ai.institutional_options.domain import (
    ContractLegRecommendation, ContractRecommendation, ContractSide,
    InstitutionalOpportunity, OpportunityLineage, OpportunityState,
    OpportunityThesis, StrategyCandidate, StrategyDisposition, ThesisDirection,
)
from trading_ai.institutional_options.valuation import ContractStrategyValuationEngine, StrategyValuationPolicy


def fixtures():
    opportunity = InstitutionalOpportunity(
        opportunity_id="opp-1", symbol="AAPL", asset_class="EQUITY",
        state=OpportunityState.CONTRACTS_OPTIMIZED, direction=ThesisDirection.BULLISH,
        category="TREND_CONTINUATION", overall_score=88, confidence=82, conviction="HIGH",
        lineage=OpportunityLineage("current_stock_intelligence", "run-1", "cand-1", "hash-1"), thesis_id="thesis-1",
    )
    thesis = OpportunityThesis(
        thesis_id="thesis-1", opportunity_id="opp-1", direction=ThesisDirection.BULLISH,
        setup_category="TREND_CONTINUATION", primary_timeframe="1d", market_regime="BULLISH",
        sector_context="LEADING", trend_state="BULLISH", structure_state="TRENDING",
        participation_state="ACCUMULATION", dealer_context="BULLISH POSITIVE_GAMMA",
        forecast_context="BULLISH", entry_zone_low=100, entry_zone_high=101,
        invalidation_level=97, targets=(108, 112),
    )
    strategy = StrategyCandidate(
        strategy_candidate_id="strat-1", opportunity_id="opp-1", strategy="LONG_CALL",
        disposition=StrategyDisposition.ELIGIBLE, eligibility_score=85, complexity="LOW",
    )
    contract = ContractRecommendation(
        contract_recommendation_id="contract-1", strategy_candidate_id="strat-1", opportunity_id="opp-1",
        option_snapshot_id="snap-1", executable=True, liquidity_score=90,
        legs=(ContractLegRecommendation("leg-1", ContractSide.BUY, "CALL", "O:AAPL261218C00105000", "2026-12-18", 105, bid=5, ask=5.2, volume=1000, open_interest=5000, delta=.55),),
    )
    return opportunity, thesis, strategy, contract


def test_valuation_produces_probability_and_expected_value():
    valued = ContractStrategyValuationEngine().value(*fixtures())
    assert valued.probability is not None
    assert 0 < valued.probability.calibrated_probability < 1
    assert valued.expected_value is not None
    assert valued.capital_required and valued.capital_required > 0


def test_valuation_rejects_non_executable_contract():
    opportunity, thesis, strategy, contract = fixtures()
    contract = ContractRecommendation(**(contract.__dict__ | {"executable": False}))
    valued = ContractStrategyValuationEngine().value(opportunity, thesis, strategy, contract)
    assert valued.disposition == StrategyDisposition.REJECTED
    assert "CONTRACT_NOT_EXECUTABLE" in valued.rejection_reasons


def test_valuation_respects_liquidity_gate():
    opportunity, thesis, strategy, contract = fixtures()
    contract = ContractRecommendation(**(contract.__dict__ | {"liquidity_score": 10}))
    valued = ContractStrategyValuationEngine(StrategyValuationPolicy(minimum_probability=.01)).value(opportunity, thesis, strategy, contract)
    assert "LIQUIDITY_BELOW_MINIMUM" in valued.rejection_reasons


def test_selected_candidate_remains_rankable_during_idempotent_rebuild():
    from trading_ai.institutional_options.valuation import _is_rankable_disposition

    assert _is_rankable_disposition(StrategyDisposition.ELIGIBLE)
    assert _is_rankable_disposition(StrategyDisposition.SELECTED)
    assert not _is_rankable_disposition(StrategyDisposition.REJECTED)

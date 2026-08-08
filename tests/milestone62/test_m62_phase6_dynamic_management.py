from trading_ai.institutional_options.domain import (
    OpportunityThesis, ProbabilityDecomposition, StrategyCandidate,
    StrategyDisposition, ThesisDirection,
)
from trading_ai.institutional_options.management import DynamicManagementPolicy, UnderlyingDrivenManagementEngine


def make(strategy="LONG_CALL", probability=.72, rr_target=108):
    thesis = OpportunityThesis(
        thesis_id="t", opportunity_id="o", direction=ThesisDirection.BULLISH,
        setup_category="TREND_CONTINUATION", primary_timeframe="1d", market_regime="BULLISH",
        sector_context="LEADING", trend_state="BULLISH", structure_state="TRENDING",
        participation_state="ACCUMULATION", dealer_context="BULLISH", forecast_context="BULLISH",
        entry_zone_low=100, entry_zone_high=101, invalidation_level=97, targets=(rr_target, 112),
        risks=("EARNINGS_PROXIMITY",),
    )
    candidate = StrategyCandidate(
        strategy_candidate_id="s", opportunity_id="o", strategy=strategy,
        disposition=StrategyDisposition.SELECTED, eligibility_score=88, strategy_score=91,
        complexity="LOW", probability=ProbabilityDecomposition(.75, .65, calibrated_probability=probability),
        selected=True, metadata={"liquidity_score": 90, "contract_recommendation_id": "c"},
    )
    return thesis, candidate


def test_management_uses_underlying_stop_targets_and_trail():
    execution, snapshot = UnderlyingDrivenManagementEngine().build(*make())
    assert execution.underlying_stop == 97
    assert execution.underlying_targets == (108, 112)
    assert execution.trailing_policy == "UNDERLYING_HIGHER_LOW"
    assert execution.ready_for_trade_builder
    assert snapshot.action in {"HOLD", "HOLD_AND_TRAIL"}


def test_long_premium_has_earlier_theta_exit():
    engine = UnderlyingDrivenManagementEngine()
    long_execution, _ = engine.build(*make("LONG_CALL"))
    spread_execution, _ = engine.build(*make("BULL_CALL_SPREAD"))
    assert long_execution.theta_exit_days_to_expiry > spread_execution.theta_exit_days_to_expiry


def test_low_integrity_recommends_exit_or_reduce():
    thesis, candidate = make(probability=.05, rr_target=102)
    candidate = StrategyCandidate(**(candidate.__dict__ | {"eligibility_score": 20, "metadata": {"liquidity_score": 5, "contract_recommendation_id": "c"}}))
    _, snapshot = UnderlyingDrivenManagementEngine(DynamicManagementPolicy(thesis_exit_threshold=.45)).build(thesis, candidate)
    assert snapshot.action in {"EXIT", "REDUCE"}


def test_partial_profit_is_governed_by_structural_rr():
    _, good = UnderlyingDrivenManagementEngine().build(*make(rr_target=110))
    _, poor = UnderlyingDrivenManagementEngine().build(*make(rr_target=102))
    assert good.partial_profit_fraction > poor.partial_profit_fraction


def test_option_specific_safeguards_are_present():
    execution, snapshot = UnderlyingDrivenManagementEngine().build(*make())
    assert execution.emergency_option_stop_pct is not None
    assert execution.volatility_exit_rule
    assert snapshot.liquidity_exit_rule
    assert snapshot.assignment_risk_rule

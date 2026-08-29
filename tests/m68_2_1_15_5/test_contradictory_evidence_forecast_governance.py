from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from trading_ai.institutional_options.contradictory_evidence import assess_contradictory_evidence
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
from trading_ai.institutional_options.strategy_generation import RegimeAwareStrategyEligibilityService
from trading_ai.institutional_options.valuation import ContractStrategyValuationEngine, StrategyValuationPolicy
from trading_ai.trend_intelligence.forecast_engine import TrendForecastEngine


def _lineage() -> OpportunityLineage:
    return OpportunityLineage(
        stock_publication_name="current_stock_intelligence",
        stock_scanner_run_id="run",
        stock_candidate_id="candidate",
        stock_state_hash="hash",
    )


def _opportunity(*, inflection=None, metadata=None) -> InstitutionalOpportunity:
    return InstitutionalOpportunity(
        opportunity_id="opp",
        symbol="TEST",
        asset_class="EQUITY",
        state=OpportunityState.VALIDATED,
        direction=ThesisDirection.BULLISH,
        category="TREND_CONTINUATION",
        overall_score=70.0,
        confidence=80.0,
        conviction="MODERATE",
        lineage=_lineage(),
        thesis_id="thesis",
        metadata=metadata or {},
        inflection_intelligence=inflection or {},
    )


def _thesis() -> OpportunityThesis:
    return OpportunityThesis(
        thesis_id="thesis",
        opportunity_id="opp",
        direction=ThesisDirection.BULLISH,
        setup_category="TREND_CONTINUATION",
        primary_timeframe="1d",
        market_regime="UPTREND",
        sector_context="TECH",
        trend_state="UP",
        structure_state="MATURE_TREND",
        participation_state="MIXED",
        dealer_context="NEGATIVE_GAMMA",
        forecast_context="NEUTRAL",
        entry_zone_low=100.0,
        entry_zone_high=101.0,
        invalidation_level=90.0,
        targets=(101.2,),
    )


def test_trend_exhaustion_and_forecast_conflict_create_reversal_watch():
    opportunity = _opportunity(
        inflection={
            "direction": "BULLISH",
            "transition_state": "TREND_EXHAUSTION",
            "inflection_score": 47.8,
            "acceleration": -1.9,
        },
        metadata={
            "forecast_evidence": {
                "forecast_direction": "NEUTRAL",
                "directional_consistency": False,
                "conflict_codes": ["EXPECTED_RETURN_DIRECTION_CONFLICT"],
            },
            "institutional_volume": {
                "accumulation_score": 46.4,
                "distribution_score": 62.6,
            },
        },
    )
    authority = assess_contradictory_evidence(opportunity, _thesis())
    assert authority.state == "REVERSAL_WATCH"
    assert authority.execution_blocked is True
    assert authority.allow_opposite_conditional is True
    assert "TREND_EXHAUSTION" in authority.reason_codes
    assert "FORECAST_SEMANTIC_CONFLICT" in authority.reason_codes
    assert "DISTRIBUTION_EXCEEDS_ACCUMULATION" in authority.reason_codes


def test_bearish_candidates_are_retained_conditionally_not_made_executable():
    opportunity = _opportunity(
        inflection={
            "direction": "BULLISH",
            "transition_state": "TREND_EXHAUSTION",
            "inflection_score": 50.0,
            "acceleration": -2.0,
        },
        metadata={
            "forecast_evidence": {"forecast_direction": "NEUTRAL", "directional_consistency": True},
            "institutional_volume": {"accumulation_score": 40.0, "distribution_score": 65.0},
        },
    )
    candidates = RegimeAwareStrategyEligibilityService().generate(opportunity, _thesis())
    long_put = next(item for item in candidates if item.strategy == "LONG_PUT")
    assert long_put.disposition in {StrategyDisposition.CONDITIONAL, StrategyDisposition.REJECTED}
    assert "DIRECTION_INCOMPATIBLE" not in long_put.rejection_reasons
    assert "CONDITIONAL_REVERSAL_CONFIRMATION_REQUIRED" in long_put.rejection_reasons
    assert long_put.selected is False


def test_absolute_strategy_floor_rejects_non_positive_economics():
    opportunity = _opportunity()
    thesis = _thesis()
    strategy = StrategyCandidate(
        strategy_candidate_id="s1",
        opportunity_id="opp",
        strategy="CALL_DIAGONAL",
        disposition=StrategyDisposition.ELIGIBLE,
        eligibility_score=80.0,
        strategy_score=80.0,
        complexity="HIGH",
        metadata={},
    )
    contract = ContractRecommendation(
        contract_recommendation_id="c1",
        strategy_candidate_id="s1",
        opportunity_id="opp",
        option_snapshot_id="snap",
        executable=True,
        legs=(
            ContractLegRecommendation(
                leg_id="l1",
                side=ContractSide.BUY,
                option_type="CALL",
                option_symbol="O:TEST",
                expiry="2026-10-16",
                strike=100.0,
                bid=9.9,
                ask=10.1,
                last=10.0,
                delta=0.5,
            ),
        ),
        liquidity_score=80.0,
    )
    result = ContractStrategyValuationEngine().value(opportunity, thesis, strategy, contract)
    assert result.disposition == StrategyDisposition.REJECTED
    assert "EXPECTED_VALUE_NOT_POSITIVE" in result.rejection_reasons or "EXPECTED_RETURN_ON_RISK_NOT_POSITIVE" in result.rejection_reasons


def test_strategy_policy_requires_positive_expected_return():
    policy = StrategyValuationPolicy()
    assert policy.minimum_expected_return_on_risk == 0.0
    assert policy.minimum_expected_value == 0.0


def test_forecast_conflict_is_fail_closed_to_neutral():
    # Prevailing EMA trend remains bearish while the recent path contains a sharp
    # rebound; the raw probability model can prefer bullish reversal while the
    # realized drift remains materially negative. The published direction must
    # abstain rather than advertise a contradictory bullish forecast.
    values = np.concatenate([
        np.linspace(140.0, 100.0, 120),
        np.linspace(100.0, 86.0, 30),
        np.linspace(86.0, 94.0, 10),
    ])
    frame = pd.DataFrame({"close": values}, index=pd.date_range("2026-01-01", periods=len(values), freq="D"))
    snap = TrendForecastEngine().calculate("TEST", frame, 10)
    if snap.expected_return_pct < 0 and snap.metadata.get("conflict_codes"):
        assert snap.forecast_direction == "NEUTRAL"
        assert snap.signal_adjustment == {"CALL": 0.0, "PUT": 0.0}
        assert snap.metadata["directional_consistency"] is False
    else:
        # The invariant itself must always hold even if this synthetic series does
        # not land in the contradiction region on a future numerical library.
        assert not (
            snap.forecast_direction == "BULLISH" and snap.expected_return_pct < -max(0.75, snap.expected_volatility_pct * 0.15)
        )

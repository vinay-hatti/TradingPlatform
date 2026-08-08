from __future__ import annotations

from trading_ai.daily.models import DailyCandidate
from trading_ai.stock_intelligence.option_integration import (
    UnderlyingOptionIntegrationPolicy,
    UnderlyingOptionIntegrationService,
)


def payload(direction="STRONG_BULLISH", *, score=88, confidence=84, quality=82, rr=2.4):
    return {
        "symbol": "CVX",
        "direction": direction,
        "structure": "EARLY_TREND",
        "primary_timeframe": "1d",
        "alignment_score": 90,
        "state_hash": "state-123",
        "scores": {"overall": score, "confidence": confidence, "primary_category": "BREAKOUT"},
        "context": {"adjustment": 4.0},
        "participation": {"deterioration_risk": 22},
        "breakout": {"failure_probability": 18},
        "trade_plan": {
            "management_quality": quality,
            "structural_reward_risk": rr,
            "entry": {"zone_low": 191.0, "zone_high": 193.0},
            "stop": {"recommended_stop": 187.5},
            "targets": {"targets": [{"price": 200}, {"price": 205}, {"price": 211}]},
            "trailing": {"method": "SWING_STRUCTURE"},
        },
    }


def service(**kwargs):
    return UnderlyingOptionIntegrationService(
        UnderlyingOptionIntegrationPolicy(enabled=True, **kwargs)
    )


def evaluate(stock=None, signal="CALL", volatility=.20, identity="O:CVX260918C00195000"):
    return service().evaluate(
        symbol="CVX",
        signal=signal,
        raw_probability=.58,
        option_volatility=volatility,
        option_liquidity_score=90,
        option_contract_identity=identity,
        stock_payload=stock,
    )


def candidate():
    return DailyCandidate(
        symbol="CVX", signal="CALL", strategy="LONG_CALL", close=193.0,
        score=80, call_score=80, put_score=20, market_regime="BULL_TREND",
        strike=195, expiry="2026-09-18", option_price=6.15, delta=.47,
        gamma=.02, theta=-.07, vega=.27, rho=0, volatility=.26, dte=46,
        final_score=80, contract_ticker="O:CVX260918C00195000", liquidity_score=90,
        ai_score=85, directional_alignment_probability=58,
    )


def test_aligned_underlying_increases_probability_and_allows_candidate():
    result = evaluate(payload())
    assert result.available and result.allowed
    assert result.adjusted_probability > result.raw_probability
    assert result.underlying_stop == 187.5
    assert result.underlying_targets == [200.0, 205.0, 211.0]


def test_direction_conflict_rejects_candidate_and_reduces_probability():
    result = evaluate(payload("STRONG_BEARISH"))
    assert not result.allowed
    assert "UNDERLYING_DIRECTION_CONFLICT" in result.rejection_reasons
    assert result.adjusted_probability < result.raw_probability


def test_missing_stock_intelligence_is_rejected_when_required():
    result = evaluate(None)
    assert not result.available and not result.allowed
    assert result.rejection_reasons == ["STOCK_INTELLIGENCE_UNAVAILABLE"]


def test_missing_contract_identity_is_rejected():
    result = evaluate(payload(), identity="")
    assert not result.allowed
    assert "OPTION_CONTRACT_IDENTITY_MISSING" in result.rejection_reasons


def test_high_iv_prefers_defined_risk_debit_spread():
    result = evaluate(payload(), volatility=.48)
    assert result.recommended_strategy == "BULL_CALL_SPREAD"


def test_low_iv_trending_setup_prefers_long_premium():
    result = evaluate(payload(), volatility=.18)
    assert result.recommended_strategy == "LONG_CALL"


def test_weak_management_plan_is_rejected():
    result = evaluate(payload(quality=20, rr=.7))
    assert not result.allowed
    assert "MANAGEMENT_QUALITY_BELOW_MINIMUM" in result.rejection_reasons
    assert "STRUCTURAL_REWARD_RISK_BELOW_MINIMUM" in result.rejection_reasons


def test_daily_candidate_contract_is_backward_compatible_by_default():
    value = candidate()
    assert value.stock_intelligence_status == "DISABLED"
    assert value.stock_intelligence_allowed is True
    assert value.underlying_targets == []


def test_probability_adjustment_is_governed_and_capped():
    result = evaluate(payload(score=100, confidence=100, quality=100, rr=5.0))
    assert abs(result.probability_adjustment) <= .12
    assert 0.01 <= result.adjusted_probability <= .99


def test_profile_edge_score_is_explainable_and_bounded():
    result = evaluate(payload())
    assert 0 <= result.edge_score <= 100
    assert len(result.evidence) >= 5
    assert any("Probability adjustment" in item for item in result.evidence)

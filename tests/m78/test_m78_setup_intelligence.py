from types import SimpleNamespace
from trading_ai.setup_intelligence.detector import GovernedSetupDetector
from trading_ai.setup_intelligence.policy import SetupIntelligencePolicy
from trading_ai.setup_intelligence.probability import HierarchicalSetupProbabilityEngine
from trading_ai.setup_intelligence.option_expression import ShadowOptionExpressionAdvisor


def candidate(**overrides):
    payload={
      "symbol":"AAPL","snapshot_timestamp":"2026-08-28T20:00:00+00:00","state_hash":"abc","direction":"STRONG_BULLISH",
      "timeframe_states":{"1d":{"direction":"BULLISH","close":105.0,"atr":5.0},"1w":{"direction":"BULLISH","close":105.0,"atr":9.0},"1mo":{"direction":"BULLISH","close":105.0,"atr":20.0}},
      "support_levels":[{"price":102.5,"strength":92}],"resistance_levels":[{"price":110,"strength":88}],
      "participation":{"state":"ACCUMULATION","score":80},
      "scores":{"bullish":90,"bearish":10,"trend_continuation":88,"reversal":72,"confidence":90,"primary_category":"BULLISH"},
      "breakout":{"state":"NONE","confirmation":0,"follow_through_probability":0,"failure_probability":50,
                  "evidence":{"resistance":110,"support":100,"relative_volume":1.1,"atr":5}},
      "context":{"market_regime":"UPTREND","gamma_regime":"NEGATIVE_GAMMA","sector_regime":"LEADING","volatility_regime":"NORMAL"},
      "metadata":{"scanner_run_id":"RUN1"}
    }
    payload.update(overrides)
    return SimpleNamespace(id="C1",scanner_run_id="RUN1",symbol="AAPL",snapshot_timestamp=payload["snapshot_timestamp"],payload_json=payload)


def test_trend_pullback_is_first_class_and_shadow_only():
    setups=GovernedSetupDetector().detect(candidate())
    pullback=[x for x in setups if x.setup_type=="TREND_PULLBACK"]
    assert pullback and pullback[0].authority_effect is False
    assert pullback[0].evidence.values["support_distance_atr"] <= .75


def test_breakout_confirmed_materialized():
    c=candidate()
    c.payload_json["breakout"]={"state":"BREAKOUT_CONFIRMED","confirmation":86,"follow_through_probability":79,"failure_probability":21,
                                "evidence":{"resistance":100,"support":92,"relative_volume":1.8,"atr":5}}
    c.payload_json["timeframe_states"]["1d"]["close"]=103
    setups=GovernedSetupDetector().detect(c)
    assert "BREAKOUT_CONFIRMED" in {x.setup_type for x in setups}


def test_breakout_retest_lifecycle_gap_closed():
    c=candidate()
    c.payload_json["breakout"]={"state":"BREAKOUT_CONFIRMED","confirmation":90,"follow_through_probability":82,"failure_probability":18,
                                "evidence":{"resistance":100,"support":92,"relative_volume":1.3,"atr":5}}
    c.payload_json["timeframe_states"]["1d"]["close"]=100.5
    previous=[{"setup_type":"BREAKOUT_CONFIRMED","stage":"CONFIRMED"}]
    setups=GovernedSetupDetector().detect(c,previous=previous)
    assert "BREAKOUT_RETEST" in {x.setup_type for x in setups}
    assert any(x.stage=="RETEST_HELD" for x in setups if x.setup_type=="BREAKOUT_RETEST")


def test_breakout_continuation_lifecycle_gap_closed():
    c=candidate()
    c.payload_json["breakout"]={"state":"BREAKOUT_CONFIRMED","confirmation":90,"follow_through_probability":82,"failure_probability":18,
                                "evidence":{"resistance":100,"support":92,"relative_volume":1.3,"atr":5}}
    c.payload_json["timeframe_states"]["1d"]["close"]=106
    setups=GovernedSetupDetector().detect(c,previous=[{"setup_type":"BREAKOUT_CONFIRMED","stage":"CONFIRMED"}])
    assert "BREAKOUT_CONTINUATION" in {x.setup_type for x in setups}


def test_failed_breakout_has_independent_identity():
    c=candidate()
    c.payload_json["direction"]="BEARISH"
    c.payload_json["breakout"]={"state":"FAILED_BREAKOUT","confirmation":80,"follow_through_probability":30,"failure_probability":88,
                                "evidence":{"resistance":110,"support":100,"relative_volume":1.5,"atr":5}}
    assert "FAILED_BREAKOUT_REVERSAL" in {x.setup_type for x in GovernedSetupDetector().detect(c)}


def test_pead_requires_explicit_point_in_time_event_evidence():
    assert not any(x.setup_family=="EVENT" for x in GovernedSetupDetector().detect(candidate()))
    c=candidate(event_intelligence={"earnings":{"event_type":"EARNINGS","surprise_score":85,"revision_score":78,"sessions_since_event":3}})
    assert "POST_EARNINGS_DRIFT_LONG" in {x.setup_type for x in GovernedSetupDetector().detect(c)}


def row(i,setup="BREAKOUT_RETEST",y=1,regime="UPTREND"):
    return SimpleNamespace(setup_type=setup,status="CLOSED",as_of=f"2026-01-{(i%28)+1:02d}",target_1_before_stop=y,
      target_2_before_stop=y,target_3_before_stop=0,profitable_at_horizon=y,maximum_favorable_excursion_pct=5 if y else 1,
      maximum_adverse_excursion_pct=1 if y else 3,realized_return_pct=3 if y else -2,days_to_target_1=5 if y else None,
      market_regime=regime,gamma_regime="NEGATIVE",sector_regime="LEADING",volatility_regime="NORMAL")


def test_probability_readiness_fails_closed():
    p=SetupIntelligencePolicy(minimum_setup_prior_observations=10,minimum_positive_observations=3,minimum_negative_observations=3,minimum_distinct_dates=5)
    assert HierarchicalSetupProbabilityEngine(p).readiness([row(i,y=1) for i in range(4)])["status"]=="INSUFFICIENT_EVIDENCE"


def test_hierarchical_model_trains_without_automatic_activation():
    p=SetupIntelligencePolicy(minimum_setup_prior_observations=10,minimum_positive_observations=3,minimum_negative_observations=3,minimum_distinct_dates=5,minimum_local_cell_observations=5)
    rows=[row(i,y=0 if i%3==0 else 1) for i in range(30)]
    artifact,evaluation=HierarchicalSetupProbabilityEngine(p).train(rows,"TEST")
    assert artifact["priors"]["BREAKOUT_RETEST"]["observation_count"]==30
    assert evaluation["automatic_activation"] is False and evaluation["authority_effect"] is False


def test_option_expression_is_blocked_without_ready_probability():
    a=ShadowOptionExpressionAdvisor().advise("BREAKOUT_RETEST",probability_status="INSUFFICIENT_EVIDENCE")
    assert a["strategy_families"]==["NO_TRADE_RESEARCH_ONLY"] and a["authority_effect"] is False


def test_policy_is_non_authoritative_by_construction():
    p=SetupIntelligencePolicy()
    assert p.authority_effect is False and p.automatic_promotion is False and p.prospective_certification_required is True

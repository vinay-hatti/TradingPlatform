from trading_ai.stock_intelligence import (
    CandidateOutcomeObservation,
    DynamicExitLearningEngine,
    OutcomeAttributionEngine,
    OutcomeTrackingEngine,
    ProbabilityCalibrationEngine,
)


def payload(prob=.7):
    return {
        'symbol':'CVX','direction':'STRONG_BULLISH','snapshot_timestamp':'2026-08-03T12:00:00Z',
        'underlying_adjusted_probability':prob,
        'scores':{'primary_category':'BREAKOUT','confidence':82},
        'context':{'market_regime':'BULL_TREND'},
        'recommended_option_strategy':'LONG_CALL',
        'trade_plan':{
            'entry':{'preferred_entry':100},
            'stop':{'recommended_stop':95},
            'targets':{'targets':[{'price':110},{'price':115}]},
        },
    }


def obs(outcome='WIN',prob=.7,ret=8,mfe=12,mae=3,policy='DYNAMIC_UNDERLYING',suffix='1'):
    return CandidateOutcomeObservation(
        observation_id='o'+suffix,candidate_id='c'+suffix,scanner_run_id='r',symbol='CVX',
        setup_category='BREAKOUT',market_regime='BULL_TREND',strategy='LONG_CALL',direction='STRONG_BULLISH',
        published_at='2026-08-03T12:00:00Z',prediction_probability=prob,entry_triggered=True,entry_price=100,
        exit_price=108,stop_price=95,target_prices=[110],maximum_favorable_excursion_pct=mfe,
        maximum_adverse_excursion_pct=mae,realized_return_pct=ret,holding_period_days=4,outcome=outcome,
        exit_reason='TARGET_ZONE_REACHED' if outcome=='WIN' else 'UNDERLYING_STRUCTURE_INVALIDATED',
        management_policy=policy,
    ).finalize()


def test_65_outcome_creation_computes_long_mfe_mae_and_return():
    value=OutcomeTrackingEngine().create_observation(candidate_payload=payload(),candidate_id='c',scanner_run_id='r',outcome='WIN',entry_triggered=True,exit_price=108,high_price=112,low_price=97,holding_period_days=4)
    assert value.maximum_favorable_excursion_pct==12
    assert value.maximum_adverse_excursion_pct==3
    assert value.realized_return_pct==8
    assert value.state_hash


def test_66_probability_is_frozen_from_candidate_payload():
    value=OutcomeTrackingEngine().create_observation(candidate_payload=payload(.73),candidate_id='c',scanner_run_id='r',outcome='WIN',entry_triggered=True)
    assert value.prediction_probability==.73


def test_67_calibration_metrics_are_bounded():
    rows=[obs('WIN',.8,suffix='1'),obs('LOSS',.6,ret=-4,suffix='2')]
    p=ProbabilityCalibrationEngine(minimum_observations=2).analyze(rows)
    assert p.valid and 0<=p.brier_score<=1 and p.log_loss>0 and 0<=p.expected_calibration_error<=1


def test_68_calibration_degrades_for_small_sample():
    p=ProbabilityCalibrationEngine(minimum_observations=20).analyze([obs()])
    assert not p.valid and 'INSUFFICIENT_CALIBRATION_SAMPLE' in p.warnings


def test_69_attribution_groups_by_setup():
    rows=[obs('WIN',suffix='1'),obs('LOSS',ret=-5,suffix='2')]
    p=OutcomeAttributionEngine().summarize(rows,'setup_category')[0]
    assert p.key=='BREAKOUT' and p.observation_count==2 and p.win_rate==50


def test_70_attribution_expectancy_and_profit_factor():
    rows=[obs('WIN',ret=10,suffix='1'),obs('LOSS',ret=-5,suffix='2')]
    p=OutcomeAttributionEngine().summarize(rows,'market_regime')[0]
    assert p.expectancy_pct==2.5 and p.profit_factor==2


def test_71_dynamic_exit_policy_comparison_ranks_better_expectancy():
    rows=[obs('WIN',ret=10,mfe=12,policy='DYNAMIC',suffix='1'),obs('LOSS',ret=-3,mfe=2,policy='DYNAMIC',suffix='2'),obs('LOSS',ret=-8,mfe=10,policy='FIXED',suffix='3')]
    out=DynamicExitLearningEngine().compare(rows)
    assert out[0].policy_name=='DYNAMIC'


def test_72_premature_exit_is_detected():
    rows=[obs('LOSS',ret=-1,mfe=8,policy='FIXED',suffix='1')]
    p=DynamicExitLearningEngine().compare(rows)[0]
    assert p.premature_exit_rate==100


def test_73_open_outcomes_are_excluded_from_binary_calibration():
    open_row=obs('OPEN',suffix='1')
    p=ProbabilityCalibrationEngine().analyze([open_row])
    assert not p.valid and p.observation_count==0


def test_74_binary_result_contract():
    assert obs('WIN',suffix='1').binary_result==1
    assert obs('LOSS',suffix='2').binary_result==0
    assert obs('BREAKEVEN',suffix='3').binary_result is None

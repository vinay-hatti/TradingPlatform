from trading_ai.stock_intelligence.decision_intelligence import InstitutionalDecisionIntelligenceEngine
from trading_ai.stock_intelligence.position_intelligence import PositionIntelligenceEngine
from trading_ai.stock_intelligence.profile import (
    StockIntelligenceProfile, TimeframeState, BreakoutProfile, InstitutionalStructureZone,
    PriceLevel, OpportunityScores, StockContextProfile, ParticipationProfile
)
from trading_ai.stock_intelligence.volume_intelligence import InstitutionalVolumeProfile
from trading_ai.trade_plan_certification import certify_stock_trade_plan


def _profile(symbol='NBIS', quality_shift=0):
    p=StockIntelligenceProfile(symbol,'2026-08-13T23:22:00+00:00',primary_timeframe='1d',direction='STRONG_BULLISH',structure='MATURE_TREND',confidence=79.8+quality_shift)
    p.timeframe_states={'1d':TimeframeState('1d','STRONG_BULLISH','MATURE_TREND',92+quality_shift,88,90,255.04,27.3524)}
    p.breakout=BreakoutProfile(state='BREAKOUT_CONFIRMED',confirmation=82+quality_shift,follow_through_probability=74+quality_shift,failure_probability=22,evidence={'resistance':232.01495,'support':145.8})
    p.structure_zones=[
        InstitutionalStructureZone('RESISTANCE',280.1054,301.9873,291.0464,70,90,.7,.3,'1mo',components=['PRICE_LEVEL','SUPPLY_ZONE'],hierarchy='PRIMARY_STRUCTURE',status='OVERHEAD',relevance_score=75),
        InstitutionalStructureZone('SUPPORT',220,235,230,82,92,.82,.18,'1d',components=['DEMAND_ZONE'],hierarchy='PRIMARY_STRUCTURE',status='BELOW_PRICE',relevance_score=88),
    ]
    p.support_levels=[PriceLevel('SUPPORT',234.4,'1d',75)]
    p.resistance_levels=[PriceLevel('RESISTANCE',232.01495,'1w',77.6),PriceLevel('RESISTANCE',299.86,'1d',100)]
    p.scores=OpportunityScores(bullish=92+quality_shift,bearish=8,overall=86+quality_shift,confidence=79.8+quality_shift,freshness=100,primary_category='ACCUMULATION')
    p.context=StockContextProfile(score=84+quality_shift,confidence=80,market_regime='UPTREND',relative_strength_grade='A+',dealer_positioning='NEUTRAL',gamma_regime='NEGATIVE_GAMMA')
    p.participation=ParticipationProfile(state='ACCUMULATION',score=82+quality_shift,conviction=80)
    p.institutional_volume=InstitutionalVolumeProfile(regime='NORMAL',signal='ACCUMULATION_CONFIRMED',institutional_participation_score=72+quality_shift,accumulation_score=78,relative_volume_1d=1.38,volume_percentile_60d=74,persistence_score=40)
    p.alignment_score=100
    p.trade_plan=PositionIntelligenceEngine().build(p)
    cert=certify_stock_trade_plan(p,p.trade_plan)
    p.trade_plan.certification=cert
    p.trade_plan.reference_market=dict(cert.get('reference_market') or {})
    p.trade_plan.finalize()
    return p


def test_decision_intelligence_builds_explainable_quality_and_barrier_prior():
    p=_profile(); engine=InstitutionalDecisionIntelligenceEngine(); a=engine.assess(p)
    assert a.version == 'M76.2-IDI-1.0'
    assert a.overall_trade_quality > 60
    assert a.decision_readiness > 55
    assert a.institutional_grade != 'NOT_CERTIFIED'
    assert a.barrier_probability.target_1_before_stop > 0
    assert a.barrier_probability.calibration_status == 'UNCALIBRATED'
    assert a.learning_snapshot['mode'] == 'SHADOW_CAPTURE'
    assert a.learning_snapshot['adaptive_influence'] is False
    assert a.evidence_registry
    assert a.passport_id.startswith('IDI-')


def test_uncertified_plan_is_fail_closed_for_decision_readiness():
    p=_profile(); p.trade_plan.certification={'status':'FAIL','quality_score':90}
    a=InstitutionalDecisionIntelligenceEngine().assess(p)
    assert a.institutional_grade == 'NOT_CERTIFIED'
    assert a.decision == 'BLOCK'
    assert a.decision_readiness <= 35
    assert 'TRADE_PLAN_NOT_CERTIFIED' in a.warnings


def test_population_competition_assigns_market_rank_and_percentile():
    engine=InstitutionalDecisionIntelligenceEngine()
    profiles=[_profile('LOW',-12),_profile('HIGH',5),_profile('MID',0)]
    for p in profiles:
        p.decision_intelligence=engine.assess(p)
    ranked=engine.rank_population(profiles)
    assert ranked[0].decision_intelligence.competition['market_rank'] == 1
    assert ranked[0].decision_intelligence.competition['population_size'] == 3
    assert ranked[-1].decision_intelligence.competition['market_rank'] == 3
    assert ranked[0].decision_intelligence.capital_priority >= ranked[-1].decision_intelligence.capital_priority


def test_stock_scanner_and_institutional_options_expose_m76_2_evidence():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    publication=(root/'src/trading_ai/stock_intelligence/publication.py').read_text()
    ingestion=(root/'src/trading_ai/institutional_options/opportunity_ingestion.py').read_text()
    ui=(root/'ui/workstation/src/StockIntelligenceScannerPage.tsx').read_text()
    io_ui=(root/'ui/workstation/src/InstitutionalOptionsPage.tsx').read_text()
    for marker in ('institutional_trade_quality','decision_readiness','capital_priority','barrier_target_1_probability','decision_intelligence'):
        assert marker in publication
    assert 'institutional_decision_intelligence' in ingestion
    assert 'Barrier prior:' in ingestion
    assert 'Institutional decision intelligence' in ui
    assert 'Institutional evidence registry' in ui
    assert 'Learning mode' in ui
    assert 'M76.2 institutional decision intelligence' in io_ui

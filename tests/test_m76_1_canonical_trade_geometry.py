from trading_ai.stock_intelligence.profile import (
    StockIntelligenceProfile, TimeframeState, BreakoutProfile, InstitutionalStructureZone,
    PriceLevel, OpportunityScores, StockContextProfile, EntryProfile, StopProfile
)
from trading_ai.stock_intelligence.position_intelligence import PositionIntelligenceEngine, DynamicTargetEngine
from trading_ai.trade_plan_certification import certify_stock_trade_plan


def _nbis_profile():
    p=StockIntelligenceProfile('NBIS','2026-08-13T23:22:00+00:00',primary_timeframe='1d',direction='STRONG_BULLISH',structure='MATURE_TREND',confidence=79.8)
    p.timeframe_states={'1d':TimeframeState('1d','STRONG_BULLISH','MATURE_TREND',100,90,100,255.04,27.3524)}
    p.breakout=BreakoutProfile(state='BREAKOUT_CONFIRMED',confirmation=80,evidence={'resistance':232.01495,'support':145.8})
    p.structure_zones=[
        InstitutionalStructureZone('RESISTANCE',220.2605,242.1424,231.2015,77.6,100,.78,.22,'1w',components=['CALL_WALL','PRICE_LEVEL','SUPPLY_ZONE'],hierarchy='DEALER_STRUCTURE',status='BROKEN'),
        InstitutionalStructureZone('RESISTANCE',280.1054,301.9873,291.0464,70,90,.7,.3,'1mo',components=['PRICE_LEVEL','SUPPLY_ZONE'],hierarchy='PRIMARY_STRUCTURE',status='OVERHEAD'),
        InstitutionalStructureZone('RESISTANCE',294.8098,302.5952,298.8633,60,80,.65,.35,'1d',components=['PRICE_LEVEL'],hierarchy='SECONDARY_STRUCTURE',status='OVERHEAD'),
        InstitutionalStructureZone('SUPPORT',129.447,151.3289,140.3879,70,90,.8,.2,'1w',components=['DEMAND_ZONE'],hierarchy='MAJOR_STRUCTURE',status='BELOW_PRICE'),
    ]
    p.support_levels=[PriceLevel('SUPPORT',234.4,'1d',75)]
    p.resistance_levels=[PriceLevel('RESISTANCE',232.01495,'1w',77.6),PriceLevel('RESISTANCE',299.86,'1d',100)]
    p.scores=OpportunityScores(confidence=79.8);p.context=StockContextProfile(confidence=75,evidence={})
    return p


def test_nbis_breakout_keeps_actual_breakout_anchor_and_does_not_use_next_supply_zone_as_entry():
    p=_nbis_profile(); plan=PositionIntelligenceEngine().build(p)
    assert plan.entry.entry_type == 'BREAKOUT'
    assert plan.entry.preferred_entry == 255.04
    assert abs(plan.entry.confirmation_trigger - 232.0149) < 1e-6
    assert plan.entry.preferred_entry != 301.9873
    assert plan.geometry_context['event_anchor'] == 232.0149
    assert plan.geometry_context['next_objective_zone']['upper_bound'] == 301.9873
    assert any('not used as the entry anchor' in x for x in plan.entry.rationale)


def test_nbis_stop_and_targets_form_one_certifiable_geometry():
    p=_nbis_profile(); plan=PositionIntelligenceEngine().build(p); cert=certify_stock_trade_plan(p,plan)
    assert plan.stop.recommended_stop < 255.04
    assert [x.price for x in plan.targets.targets] == [280.1054,294.8098,299.86]
    assert all(x.price > plan.entry.zone_high for x in plan.targets.targets)
    assert cert['status'] == 'PASS'
    assert cert['failure_codes'] == []


def test_target_engine_rejects_objective_above_current_but_behind_final_bullish_entry():
    p=_nbis_profile()
    # Synthetic future entry proves target filtering is against final entry, not only current price.
    entry=EntryProfile(entry_type='BREAKOUT',preferred_entry=301.9873,zone_low=301.2,zone_high=302.75)
    stop=StopProfile(recommended_stop=250.0,selected_type='STRUCTURE',confidence=80)
    targets=DynamicTargetEngine().build(p,entry,stop)
    primary=[x.price for x in targets.targets]
    assert 280.1054 not in primary and 294.8098 not in primary and 299.86 not in primary
    rejected={x['price']:x['selection_reason'] for x in targets.rejected_targets}
    assert rejected[280.1054] == 'BEHIND_FINAL_ENTRY_ZONE'
    assert all(x > entry.zone_high for x in primary)


def test_bearish_breakdown_is_exact_inverse():
    p=StockIntelligenceProfile('BEAR','2026-08-13T23:22:00+00:00',primary_timeframe='1d',direction='STRONG_BEARISH',structure='MATURE_TREND',confidence=80)
    p.timeframe_states={'1d':TimeframeState('1d','STRONG_BEARISH','MATURE_TREND',90,80,90,100,5)}
    p.breakout=BreakoutProfile(state='BREAKDOWN_CONFIRMED',evidence={'resistance':110,'support':105})
    p.structure_zones=[InstitutionalStructureZone('SUPPORT',80,90,85,80,90,.8,.2,'1d',components=['DEMAND_ZONE'],hierarchy='PRIMARY_STRUCTURE',status='BELOW_PRICE'),InstitutionalStructureZone('RESISTANCE',108,112,110,80,90,.8,.2,'1d',components=['SUPPLY_ZONE'],hierarchy='PRIMARY_STRUCTURE',status='OVERHEAD')]
    p.support_levels=[PriceLevel('SUPPORT',105,'1d',80),PriceLevel('SUPPORT',88,'1d',80)];p.resistance_levels=[PriceLevel('RESISTANCE',110,'1d',80)]
    p.scores=OpportunityScores(confidence=80);p.context=StockContextProfile(confidence=80,evidence={})
    plan=PositionIntelligenceEngine().build(p);cert=certify_stock_trade_plan(p,plan)
    assert plan.entry.preferred_entry == 100
    assert plan.entry.confirmation_trigger == 105
    assert plan.stop.recommended_stop > 100
    assert all(x.price < plan.entry.zone_low for x in plan.targets.targets)
    assert cert['status'] == 'PASS'

from types import SimpleNamespace

from trading_ai.stock_intelligence.position_intelligence import DynamicTargetEngine
from trading_ai.stock_intelligence.profile import EntryProfile, InstitutionalStructureZone, PriceLevel, StopProfile


def bearish_case():
    profile = SimpleNamespace(
        primary_timeframe='1d', direction='STRONG_BEARISH',
        timeframe_states={'1d': SimpleNamespace(close=133.89, atr=10.221057142857143)},
        structure_zones=[InstitutionalStructureZone(
            'SUPPORT',99.4969,107.6738,103.5854,83.52,87.0,.8146,.1854,'1d',['1d'],
            ['DEMAND_ZONE','PRICE_LEVEL','PUT_WALL'],6,'FRESH','DEALER_STRUCTURE','BELOW_PRICE',-19.1,67.45,{},{}
        )],
        support_levels=[PriceLevel('SUPPORT',105.5567,'1d',89.6,75.2,3,.7845,.2155)],
        resistance_levels=[],
        context=SimpleNamespace(evidence={'dealer_levels':{
            'gamma_flip':135.315007,'primary_put_wall':100.0,'primary_call_wall':130.0,'confidence_score':99.5,
        }}),
    )
    result=DynamicTargetEngine().build(profile,EntryProfile(preferred_entry=142.8758),StopProfile(recommended_stop=147.9863))
    prices=[x.price for x in result.targets]
    assert len(prices)==3, prices
    assert prices==sorted(prices,reverse=True), prices
    assert all(x<142.8758 for x in prices), prices
    assert result.additional_targets, 'additional target map missing'
    assert all(x['price']<142.8758 for x in result.additional_targets)
    assert result.ranking_version=='M70-TARGET-RANKING-1.0'
    primary_rationale=' '.join(y for x in result.targets for y in x.rationale)
    assert 'GAMMA_FLIP' in primary_rationale or any(x['source_type']=='GAMMA_FLIP' for x in result.additional_targets)
    # 135.21-class fallback must retain explicit provenance, whether merged into a stronger nearby target or additional.
    all_add=result.additional_targets
    fallback_visible=any(
        x['source_type']=='RISK_EXPANSION_1_5R' or 'RISK_EXPANSION_1_5R' in x.get('merged_sources',[])
        for x in all_add
    ) or any('1.5R risk-expansion fallback' in ' '.join(x.rationale) for x in result.targets)
    assert fallback_visible


def bullish_case():
    profile = SimpleNamespace(
        primary_timeframe='1d', direction='STRONG_BULLISH',
        timeframe_states={'1d': SimpleNamespace(close=100.0, atr=4.0)},
        structure_zones=[InstitutionalStructureZone(
            'RESISTANCE',108.0,110.0,109.0,85.0,80.0,.78,.22,'1d',['1d'],['PRICE_LEVEL','SUPPLY_ZONE'],3,'FRESH','PRIMARY_STRUCTURE','OVERHEAD',9.0,75.0,{},{}
        )],
        resistance_levels=[PriceLevel('RESISTANCE',115.0,'1d',80.0,70.0,2,.72,.28)],
        support_levels=[],
        context=SimpleNamespace(evidence={'dealer_levels':{'gamma_flip':105.0,'primary_call_wall':120.0,'primary_put_wall':90.0,'confidence_score':90.0}}),
    )
    result=DynamicTargetEngine().build(profile,EntryProfile(preferred_entry=100.0),StopProfile(recommended_stop=95.0))
    prices=[x.price for x in result.targets]
    assert len(prices)==3, prices
    assert prices==sorted(prices), prices
    assert all(x>100.0 for x in prices), prices
    assert all(x['price']>100.0 for x in result.additional_targets)
    assert any(x['source_type']=='PUT_WALL' for x in result.rejected_targets), result.rejected_targets


if __name__=='__main__':
    bearish_case(); bullish_case()
    print('Stock target intelligence governed ranking acceptance: PASS')

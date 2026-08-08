from types import SimpleNamespace

from trading_ai.stock_intelligence import InstitutionalStructureZoneEngine, StockIntelligenceService
from trading_ai.stock_intelligence.models import StockInstitutionalStructureZoneModel


def bars(start=100.0,count=150,step=.18):
    result=[]
    for i in range(count):
        close=start+i*step+(i%8-4)*.09
        result.append({'open':close-.15,'high':close+.75,'low':close-.75,'close':close,'volume':100000+i*300})
    return result


def context():
    return {
        'trend':SimpleNamespace(short_term_trend='BULLISH',relative_strength_vs_spy=2.0,relative_strength_grade='B'),
        'market_regime':SimpleNamespace(regime='BULL_TREND'),
        'forecast':SimpleNamespace(direction='BULLISH'),
        'dealer':SimpleNamespace(positioning_label='BULLISH',gamma_regime='NEGATIVE_GAMMA',gamma_flip=120.0,primary_call_wall=132.0,primary_put_wall=118.0,confidence_score=85.0),
        'institutional':SimpleNamespace(participation_score=72.0,participation_state='ACCUMULATION'),
    }


def profile():
    return StockIntelligenceService().analyze('XYZ',{'1d':bars(),'1w':bars(step=.8),'1mo':bars(step=2.5)},'t',context())


def test_structure_zones_cluster_duplicate_raw_levels():
    p=profile()
    assert p.structure_zones
    assert len([z for z in p.structure_zones if z.zone_type=='SUPPORT'])<=5
    assert len([z for z in p.structure_zones if z.zone_type=='RESISTANCE'])<=5
    assert all(z.lower_bound<=z.representative_price<=z.upper_bound for z in p.structure_zones)


def test_structure_zones_include_dealer_components():
    p=profile()
    components={component for zone in p.structure_zones for component in zone.components}
    assert {'PUT_WALL','CALL_WALL','GAMMA_FLIP'} & components


def test_position_plan_uses_canonical_structure_zones():
    p=profile()
    assert p.trade_plan.entry.rationale
    assert any('structure zone' in item.lower() for item in p.trade_plan.entry.rationale)
    assert any(candidate.stop_type=='INSTITUTIONAL_STRUCTURE' for candidate in p.trade_plan.stop.candidates)


def test_structure_zone_model_registered():
    assert StockInstitutionalStructureZoneModel.__tablename__=='stock_institutional_structure_zones'
    for name in ('zone_type','lower_bound','upper_bound','representative_price','confluence_score','components'):
        assert name in StockInstitutionalStructureZoneModel.__table__.columns


def test_structure_zone_hierarchy_status_distance_and_distinct_metrics():
    p=profile()
    assert any(z.hierarchy=='PRIMARY_STRUCTURE' for z in p.structure_zones)
    assert all(z.status in {'ACTIVE','BELOW_PRICE','OVERHEAD','BROKEN'} for z in p.structure_zones)
    assert all(isinstance(z.distance_pct,float) for z in p.structure_zones)
    assert all(0 <= z.relevance_score <= 100 for z in p.structure_zones)
    assert any(abs(z.strength-z.confluence_score) > 0.01 for z in p.structure_zones)


def test_dealer_structure_zone_has_rich_context():
    p=profile()
    dealer=[z for z in p.structure_zones if {'PUT_WALL','CALL_WALL','GAMMA_FLIP'} & set(z.components)]
    assert dealer
    assert all('confidence_score' in z.dealer_context for z in dealer)
    assert any(z.hierarchy=='DEALER_STRUCTURE' for z in dealer)

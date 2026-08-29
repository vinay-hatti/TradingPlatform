from datetime import date
from trading_ai.institutional_market_structure import DealerPositioningPolicy,InstitutionalMarketStructureEngine,scanner_context
from trading_ai.institutional_market_structure.serialization import snapshot_from_dict

def r(q,e,k,t,oi,d,g,iv=.25,bid=1.0,ask=1.2,vol=100):
    return {'quote_date':q,'expiry':e,'strike':k,'option_type':t,'open_interest':oi,'volume':vol,'implied_volatility':iv,'delta':d,'gamma':g,'bid':bid,'ask':ask,'last':1.1}
rows=[
 r(date(2026,7,23),date(2026,8,21),95,'PUT',9000,-.30,.025,.30),
 r(date(2026,7,23),date(2026,8,21),100,'CALL',8000,.52,.04,.24),
 r(date(2026,7,23),date(2026,8,21),100,'PUT',6000,-.48,.04,.28),
 r(date(2026,7,23),date(2026,8,21),105,'CALL',12000,.28,.03,.27),
 # Must be ignored: a second, older snapshot must never be mixed.
 r(date(2026,7,22),date(2026,8,21),150,'CALL',999999,.05,.001,.50),
]
p=DealerPositioningPolicy(confidence_minimum_rows=1,confidence_minimum_oi=1,gamma_grid_steps=51)
s=InstitutionalMarketStructureEngine(p).analyze('TEST',date(2026,7,24),100,rows,.20)
assert s.option_snapshot_date=='2026-07-23'
assert s.source_contract_count==4
assert s.primary_call_wall==105
assert s.primary_put_wall==95
assert s.quote_coverage_pct==100
assert {x.metric_class for x in s.provenance}=={'COMPUTED','MODEL_DERIVED','ESTIMATED'}
assert s.estimator_name=='OI_GREEKS_DEALER_POSITION_PROXY'
assert 'not directly reported dealer inventory' in s.assumptions[0]
assert len(s.iv_surface)==4
assert abs((s.bull_probability+s.bear_probability)-100)<1e-8
round_trip=snapshot_from_dict(s.to_dict())
assert round_trip.to_dict()==s.to_dict()
ctx=scanner_context(s,'CALL')
assert ctx['market_structure_snapshot_date']=='2026-07-23'
assert -15<=ctx['scanner_score_adjustment']<=15
print('Milestone 44 persisted-snapshot architecture assertions passed.')

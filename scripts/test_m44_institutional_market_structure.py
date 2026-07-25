from datetime import date
from trading_ai.institutional_market_structure import DealerPositioningPolicy, InstitutionalMarketStructureEngine

def row(strike,right,oi,volume,delta,gamma,iv=.25,expiry="2026-08-21"):
    return {"quote_date":date(2026,7,23),"expiry":date.fromisoformat(expiry),"strike":strike,"option_type":right,"open_interest":oi,"volume":volume,"implied_volatility":iv,"delta":delta,"gamma":gamma,"bid":2.0,"ask":2.2,"last":2.1}
rows=[row(95,"PUT",8000,600,-.25,.025,.30),row(100,"CALL",10000,900,.52,.04,.24),row(100,"PUT",5000,500,-.48,.04,.28),row(105,"CALL",12000,1200,.28,.03,.27),row(110,"CALL",3000,300,.15,.015,.31)]
s=InstitutionalMarketStructureEngine(DealerPositioningPolicy(confidence_minimum_rows=1,confidence_minimum_oi=1)).analyze("TEST",date(2026,7,24),100.0,rows,.20)
assert s.call_wall==105
assert s.put_wall==95
assert s.option_snapshot_date=="2026-07-23"
assert s.expected_move and s.expected_move>0
assert 1<=s.bull_probability<=98 and 1<=s.range_probability<=98
assert s.estimator_name=="OI_GREEKS_DEALER_POSITION_PROXY"
assert any("not directly reported" in x for x in s.assumptions)
assert len(s.strike_exposures)==4
print("Milestone 44 institutional market structure assertions passed.")

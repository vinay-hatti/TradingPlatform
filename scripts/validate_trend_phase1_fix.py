from trading_ai.trend_intelligence.service import SECTOR_ETFS
from trading_ai.trend_intelligence.repository import TrendIntelligenceRepository

EXPECTED={"Information Technology":"XLK","Consumer Discretionary":"XLY","Financials":"XLF","Health Care":"XLV","Materials":"XLB"}
for sector, etf in EXPECTED.items():
    assert SECTOR_ETFS.get(sector)==etf, (sector,SECTOR_ETFS.get(sector))
repo=object.__new__(TrendIntelligenceRepository)
repo.latest=lambda symbol:{'as_of_date':'2026-07-24','short_term':{'state':'STRONG_BULLISH'},'intermediate_term':{'state':'BULLISH'},'long_term':{'state':'STRONG_BULLISH'},'alignment_score':95,'signal_alignment':{'CALL':96,'PUT':18},'trend_quality_score':90,'trend_confidence':92,'trend_stage':'EARLY_TREND','trend_age_days':8,'relative_strength_vs_spy':7,'relative_strength_vs_sector':4,'relative_strength_grade':'A','sector_alignment_score':85,'market_alignment_score':88}
ctx=repo.scanner_context('TEST','CALL',3,reference_date='2026-07-24')
assert ctx['trend_context_status']=='FRESH'
assert ctx['trend_snapshot_age_days']==0
assert ctx['trend_score_adjustment']>0
print('Phase 1 fix validation assertions passed.')

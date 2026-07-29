from trading_ai.trend_intelligence.repository import TrendIntelligenceRepository

def snapshot(as_of='2026-07-24'):
    return {'as_of_date':as_of,'short_term':{'state':'STRONG_BULLISH'},'intermediate_term':{'state':'BULLISH'},'long_term':{'state':'STRONG_BULLISH'},'alignment_score':95,'signal_alignment':{'CALL':96,'PUT':18},'trend_quality_score':90,'trend_confidence':92,'trend_stage':'EARLY_TREND','trend_age_days':8,'relative_strength_vs_spy':7,'relative_strength_vs_sector':4,'relative_strength_grade':'A','sector_alignment_score':85,'market_alignment_score':88}

def main():
    repo=object.__new__(TrendIntelligenceRepository)
    repo.latest=lambda symbol:snapshot()
    call=repo.scanner_context('TEST','CALL',3,reference_date='2026-07-24')
    put=repo.scanner_context('TEST','PUT',3,reference_date='2026-07-24')
    assert call['trend_context_status']=='FRESH' and call['trend_snapshot_age_days']==0
    assert call['trend_score_adjustment'] > 0
    assert put['trend_score_adjustment'] < 0
    stale=repo.scanner_context('TEST','CALL',3,reference_date='2026-07-28')
    assert stale['trend_context_status']=='STALE'
    print('All Trend Intelligence scanner integration assertions passed.')
if __name__=='__main__':main()

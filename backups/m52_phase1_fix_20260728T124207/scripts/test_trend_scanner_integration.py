from trading_ai.trend_intelligence.repository import TrendIntelligenceRepository

def main():
 repo=object.__new__(TrendIntelligenceRepository)
 repo.latest=lambda symbol:{
  'as_of_date':'2099-01-01','short_term':{'state':'STRONG_BULLISH'},'intermediate_term':{'state':'BULLISH'},'long_term':{'state':'STRONG_BULLISH'},
  'alignment_score':95,'signal_alignment':{'CALL':96,'PUT':18},'trend_quality_score':90,'trend_confidence':92,'trend_stage':'EARLY_TREND','trend_age_days':8,
  'relative_strength_vs_spy':7,'relative_strength_vs_sector':4,'relative_strength_grade':'A','sector_alignment_score':85,'market_alignment_score':88}
 call=repo.scanner_context('TEST','CALL',99999); put=repo.scanner_context('TEST','PUT',99999)
 assert call['trend_score_adjustment'] > 0
 assert put['trend_score_adjustment'] < call['trend_score_adjustment']
 assert call['short_term_trend']=='STRONG_BULLISH'
 print('All Trend Intelligence scanner integration assertions passed.')
if __name__=='__main__':main()

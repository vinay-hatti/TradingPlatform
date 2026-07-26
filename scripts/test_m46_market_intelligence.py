from datetime import date,timedelta
import math
from trading_ai.market_intelligence.engine import returns_matrix,correlation_analytics,sector_breadth,market_internals,sentiment_ensemble,dealer_changes,risk_dashboard,opportunities
from trading_ai.market_intelligence.integration import intelligence_adjustments

rows=[]; start=date(2026,1,1)
for i in range(90):
 for j,(s,sec) in enumerate([('AAA','Information Technology'),('BBB','Information Technology'),('CCC','Financials'),('DDD','Financials')]):
  base=100+j*10; trend=i*(.2 if j<2 else -.05); wave=math.sin(i/5+j)*1.5
  close=base+trend+wave
  rows.append({'symbol':s,'date':start+timedelta(days=i),'close':close,'volume':1_000_000+i*1000+j*500})
mem={s:{'sector':sec} for s,sec in [('AAA','Information Technology'),('BBB','Information Technology'),('CCC','Financials'),('DDD','Financials')]}
ret=returns_matrix(rows,60); c=correlation_analytics(ret,{s:x['sector'] for s,x in mem.items()})
assert c['status']=='READY' and -1<=c['average_pairwise_correlation']<=1
assert all(x['symbol_a']!=x['symbol_b'] for x in c['pairs'])
sec=sector_breadth(rows,mem); assert len(sec)==2 and all(0<=x['breadth_score']<=100 for x in sec)
mi=market_internals(rows); assert mi['status']=='READY' and mi['tick_status']=='DATA_BLOCKED'
dealer=dealer_changes([{'symbol':'SPY','as_of_date':'2026-07-23','institutional_positioning_score':55,'net_gamma_exposure':10,'net_delta_exposure':20,'net_vanna_exposure':1,'net_charm_exposure':2,'primary_call_wall':600,'primary_put_wall':580,'gamma_flip':590,'confidence_score':.8},{'symbol':'SPY','as_of_date':'2026-07-24','institutional_positioning_score':65,'net_gamma_exposure':12,'net_delta_exposure':25,'net_vanna_exposure':2,'net_charm_exposure':1,'primary_call_wall':605,'primary_put_wall':582,'gamma_flip':594,'confidence_score':.9,'positioning_label':'BULLISH','gamma_regime':'POSITIVE','range_probability':.5,'breakout_probability':.4,'breakdown_probability':.1}])
assert dealer[0]['call_wall_migration']==5 and dealer[0]['provenance']=='ESTIMATED'
ov={'trend_score':65,'breadth_score':60,'momentum_score':62,'risk_on_score':60,'liquidity_score':70,'confidence_score':85,'regime_transition_probability':30,'volatility_risk':35,'credit_score':55,'rates_score':50,'dollar_score':50,'options_score':60}
sent=sentiment_ensemble(ov,c,mi,sec,dealer); assert len(sent['components'])==14 and 0<=sent['overall_sentiment_score']<=100
risk=risk_dashboard(c,sent,mi,sec,dealer,ov); assert len(risk['components'])==12
opp=opportunities(sec,dealer,sent,risk,ov); assert opp
ctx={'status':'FRESH','market_risk_score':70,'correlation_regime':'HIGH_CORRELATION','sentiment_score':60,'sector_context':{'Information Technology':sec[0]}}
adj=intelligence_adjustments(ctx,'Information Technology','CALL'); assert adj['risk_score_adjustment']<0
print('Milestone 46 market intelligence assertions passed.')

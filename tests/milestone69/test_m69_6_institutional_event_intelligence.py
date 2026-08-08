from trading_ai.option_valuation_intelligence.events.analytics import *
def test_distribution_weights():
 d=distribution([1,2,3,4,5]);assert d.sample_size==5 and d.median==3
 x,w=weighted_expected_move(8,6,None);assert round(x,4)==round((8*.55+6*.30)/.85,4) and w['forecast']==0
def test_variance_confidence_edge():
 assert event_variance_move(.4,30,.3,20)>0
 assert confidence_score(date_confirmed=True,time_confirmed=True,implied=True,historical_samples=8,forecast=True,liquidity_score=80,agreement_score=85,source_fresh=True)>=80
 assert classify_event_edge(5,6,80)=='UNDERPRICED_EVENT'

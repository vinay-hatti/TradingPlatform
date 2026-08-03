from trading_ai.performance_learning.service import PerformanceLearningService
rows=[]
for i in range(20):
 rows.append({'strategy':'TREND' if i<10 else 'REVERSAL','direction':'BULLISH' if i%2==0 else 'BEARISH','realized_return_pct':3.0 if i<7 else (-2.0 if i<10 else (-1.0 if i<18 else 2.0)),'predicted_probability':.72 if i<10 else .58,'decision_followed':i%5!=0,'recommended_action':'HOLD' if i<10 else 'CLOSE'})
r=PerformanceLearningService.build_report(rows)
assert r.overall.sample_size==20
assert 'TREND' in r.by_strategy and 'REVERSAL' in r.by_strategy
assert len(r.calibration)>0
assert r.decision_quality.override_rate>0
assert r.governance['automatic_activation'] is False
assert r.governance['maximum_weight_change_pct']==15
assert any(x.target=='REVERSAL' for x in r.recommendations)
print('Milestone 58 Performance Analytics & Continuous Learning assertions passed.')

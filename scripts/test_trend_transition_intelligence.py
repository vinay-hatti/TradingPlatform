import numpy as np, pandas as pd
from trading_ai.trend_intelligence.transition_engine import TrendTransitionEngine
def frame(kind):
 n=180; x=np.arange(n); base=100+x*.12
 if kind=='up': close=base.copy(); close[-1]=close[:-1].max()*1.02
 elif kind=='down': close=base[::-1].copy(); close[-1]=close[:-1].min()*.98
 else: close=100+np.sin(x/6)
 return pd.DataFrame({'date':pd.date_range('2026-01-01',periods=n),'close':close})
def main():
 e=TrendTransitionEngine(); up=e.analyze('UP',frame('up'),{'alignment_score':90,'trend_quality_score':85,'trend_age_days':20}); assert up.breakout_state=='CONFIRMED_BREAKOUT'; assert up.signal_adjustment['CALL']>0; assert up.signal_adjustment['PUT']<0
 dn=e.analyze('DN',frame('down'),{'alignment_score':90,'trend_quality_score':85,'trend_age_days':20}); assert dn.breakout_state=='CONFIRMED_BREAKDOWN'; assert dn.signal_adjustment['PUT']>0; assert dn.signal_adjustment['CALL']<0
 assert abs(up.signal_adjustment['CALL'])<=2 and abs(dn.signal_adjustment['PUT'])<=2
 print('All Trend Transition Intelligence assertions passed.')
if __name__=='__main__':main()

from datetime import date,timedelta
import pandas as pd
from trading_ai.trend_intelligence.engine import TrendIntelligenceEngine

def frame(mult=1.0,n=260):
 start=date(2025,1,1); rows=[]
 for i in range(n): rows.append({'date':start+timedelta(days=i),'close':100*mult*(1.0015**i),'volume':1_000_000+i})
 return pd.DataFrame(rows)

def main():
 snap=TrendIntelligenceEngine().analyze('TEST',frame(),benchmark=frame(.8),sector_prices=frame(.9),sector='Technology',sector_etf='XLK')
 assert snap.long_term.direction=='UP'
 assert snap.intermediate_term.direction=='UP'
 assert snap.short_term.direction=='UP'
 assert snap.signal_alignment['CALL'] > snap.signal_alignment['PUT']
 assert 0 <= snap.alignment_score <= 100
 assert snap.relative_strength_grade in {'A+','A','B','C','D','F'}
 print('All Trend Intelligence engine assertions passed.')
if __name__=='__main__':main()

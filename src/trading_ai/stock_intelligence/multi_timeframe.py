from __future__ import annotations
from math import sqrt
from .profile import *

def _rows(data):
    if hasattr(data,'to_dict'): return data.to_dict('records')
    return list(data or [])
def _ema(vals,n):
    if not vals:return 0.
    a=2/(n+1); x=float(vals[0])
    for v in vals[1:]:x=a*float(v)+(1-a)*x
    return x
def _atr(rows,n=14):
    tr=[]
    for i,r in enumerate(rows):
        pc=float(rows[i-1]['close']) if i else float(r['close']); tr.append(max(float(r['high'])-float(r['low']),abs(float(r['high'])-pc),abs(float(r['low'])-pc)))
    return sum(tr[-n:])/max(1,len(tr[-n:]))
class TimeframeStateEngine:
    def analyze(self,timeframe,data):
        rows=_rows(data)
        if len(rows)<20: raise ValueError(f'insufficient history for {timeframe}')
        c=[float(r['close']) for r in rows]; close=c[-1]; e8=_ema(c[-40:],8); e21=_ema(c[-60:],21); e50=_ema(c[-100:],50)
        ret=(close/c[-11]-1)*100 if len(c)>10 else 0; slope=(e8/e21-1)*100 if e21 else 0
        changes=[abs(c[i]-c[i-1]) for i in range(1,len(c))]; er=abs(c[-1]-c[max(0,len(c)-20)])/max(1e-9,sum(changes[-19:]))
        score=max(-100,min(100,slope*18+ret*3+(25 if e8>e21>e50 else -25 if e8<e21<e50 else 0)))
        if score>=55:d=Direction.STRONG_BULLISH.value
        elif score>=20:d=Direction.BULLISH.value
        elif score>=5:d=Direction.WEAK_BULLISH.value
        elif score<=-55:d=Direction.STRONG_BEARISH.value
        elif score<=-20:d=Direction.BEARISH.value
        elif score<=-5:d=Direction.WEAK_BEARISH.value
        else:d=Direction.NEUTRAL.value
        atr=_atr(rows); ranges=[float(r['high'])-float(r['low']) for r in rows]
        recent=sum(ranges[-10:])/10; prior=sum(ranges[-30:-10])/20 if len(ranges)>=30 else recent
        if recent<prior*.7:s=Structure.COMPRESSION.value
        elif recent>prior*1.35:s=Structure.EXPANSION.value
        elif abs(score)<12:s=Structure.SIDEWAYS.value
        elif er>.55:s=Structure.EARLY_TREND.value
        elif er>.3:s=Structure.TRENDING.value
        else:s=Structure.MATURE_TREND.value
        rets=[c[i]/c[i-1]-1 for i in range(1,len(c)) if c[i-1]]; rv=(sum(x*x for x in rets[-20:])/max(1,len(rets[-20:])))**.5*sqrt(252)*100
        return TimeframeState(timeframe,d,s,round(abs(score),2),round(max(0,min(100,50+ret*5)),2),round(min(100,55+len(rows)/4),2),close,round(atr,4),round(rv,2),round(er,4),{'ema8':e8,'ema21':e21,'ema50':e50,'return10_pct':ret})
class MultiTimeframeTrendStructureService:
    weights={'5m':.05,'15m':.1,'30m':.1,'1h':.2,'1d':.35,'1w':.2}
    signed={'STRONG_BULLISH':1,'BULLISH':.7,'WEAK_BULLISH':.3,'NEUTRAL':0,'WEAK_BEARISH':-.3,'BEARISH':-.7,'STRONG_BEARISH':-1}
    def __init__(self,engine=None):self.engine=engine or TimeframeStateEngine()
    def analyze(self,data_by_timeframe):
        states={}; warnings=[]
        for tf,data in data_by_timeframe.items():
            try:states[tf]=self.engine.analyze(tf,data)
            except ValueError as e:warnings.append(str(e))
        if not states: raise ValueError('no usable timeframe history')
        total=sum(self.weights.get(k,.1) for k in states); signed=sum(self.weights.get(k,.1)*self.signed[v.direction] for k,v in states.items())/total
        direction=Direction.STRONG_BULLISH.value if signed>.72 else Direction.BULLISH.value if signed>.25 else Direction.STRONG_BEARISH.value if signed<-.72 else Direction.BEARISH.value if signed<-.25 else Direction.NEUTRAL.value
        primary='1d' if '1d' in states else max(states,key=lambda k:self.weights.get(k,0))
        return {'states':states,'direction':direction,'structure':states[primary].structure,'alignment_score':round(abs(signed)*100,2),'confidence':round(sum(x.confidence for x in states.values())/len(states),2),'primary_timeframe':primary,'warnings':warnings,'hash':stable_hash({k:v.__dict__ for k,v in states.items()})}

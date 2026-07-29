from __future__ import annotations
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from .transition_contracts import TrendTransitionSnapshot
from .transition_policy import TrendTransitionPolicy

def clamp(v,lo=0.0,hi=100.0): return max(lo,min(float(v),hi))
def pct(a,b): return (a/b-1.0)*100.0 if b else 0.0

class TrendTransitionEngine:
    VERSION='trend_transition.v1'
    def __init__(self,policy=None): self.policy=policy or TrendTransitionPolicy()
    def analyze(self,symbol,prices,phase1_snapshot=None):
        df=prices.copy(); df.columns=[str(c).lower() for c in df.columns]
        df=df.sort_values('date').drop_duplicates('date')
        close=pd.to_numeric(df['close'],errors='coerce').dropna()
        if len(close)<self.policy.minimum_history_days:
            raise ValueError(f'insufficient transition history for {symbol}: {len(close)} rows')
        p=self.policy; px=float(close.iloc[-1]); prior=close.iloc[:-1]
        window=prior.tail(p.channel_lookback)
        hi=float(window.max()); lo=float(window.min()); span=max(hi-lo,1e-12)
        channel=clamp((px-lo)/span*100.0)
        up_dist=pct(px,hi); down_dist=pct(px,lo)
        if up_dist>=p.breakout_buffer_pct: breakout='CONFIRMED_BREAKOUT'; direction='UP'; distance=up_dist
        elif down_dist<=-p.breakout_buffer_pct: breakout='CONFIRMED_BREAKDOWN'; direction='DOWN'; distance=abs(down_dist)
        elif channel>=90: breakout='BREAKOUT_WATCH'; direction='UP'; distance=abs(up_dist)
        elif channel<=10: breakout='BREAKDOWN_WATCH'; direction='DOWN'; distance=abs(down_dist)
        else: breakout='IN_CHANNEL'; direction='NEUTRAL'; distance=0.0
        ret=close.pct_change()*100.0
        fast=float(ret.tail(p.momentum_fast).mean()); slow=float(ret.tail(p.momentum_slow).mean())
        accel=clamp(50.0+(fast-slow)*18.0)
        rolling_vol=ret.rolling(20).std()*np.sqrt(252)
        valid=rolling_vol.dropna().tail(p.volatility_lookback)
        current=float(valid.iloc[-1]) if len(valid) else 0.0
        vol_pct=float((valid<=current).mean()*100.0) if len(valid) else 50.0
        if vol_pct<=25: vol_state='COMPRESSION'
        elif vol_pct>=75: vol_state='EXPANSION'
        else: vol_state='NORMAL'
        compression=clamp(100.0-vol_pct)
        p1=phase1_snapshot or {}; stage=str(p1.get('trend_stage',''))
        align=float(p1.get('alignment_score',50)); quality=float(p1.get('trend_quality_score',50)); age=int(p1.get('trend_age_days',0))
        exhaustion=clamp((age-45)*0.55 + max(0,channel-85)*1.8 + max(0,85-quality)*0.5) if direction!='DOWN' else clamp((age-45)*0.55+max(0,15-channel)*1.8+max(0,85-quality)*0.5)
        reversal=clamp(abs(fast-slow)*14 + (100-align)*0.55 + (25 if 'EXHAUSTION' in stage else 0))
        confirmation=clamp(align*.35+quality*.25+abs(accel-50)*.45+(20 if breakout.startswith('CONFIRMED') else 8 if 'WATCH' in breakout else 0)-exhaustion*.18-reversal*.12)
        if breakout=='CONFIRMED_BREAKOUT': state='BULLISH_TRANSITION'
        elif breakout=='CONFIRMED_BREAKDOWN': state='BEARISH_TRANSITION'
        elif exhaustion>=70: state='EXHAUSTION_RISK'
        elif reversal>=70: state='REVERSAL_RISK'
        elif vol_state=='COMPRESSION' and ('WATCH' in breakout): state='COILED_TRANSITION'
        else: state='CONTINUATION'
        base=(confirmation-50)*0.04
        call=base if direction!='DOWN' else -abs(base)-0.5
        put=base if direction=='DOWN' else -abs(base)-0.5 if direction=='UP' else 0.0
        risk=max(exhaustion,reversal)
        if risk>=70:
            call-=min(1.5,(risk-60)*.04); put-=min(1.5,(risk-60)*.04)
        cap=p.maximum_transition_adjustment
        call=max(-cap,min(cap,call)); put=max(-cap,min(cap,put))
        asof=str(pd.to_datetime(df['date']).max().date())
        return TrendTransitionSnapshot(symbol,asof,datetime.now(timezone.utc),state,direction,breakout,round(channel,2),round(distance,4),round(accel,2),vol_state,round(vol_pct,2),round(compression,2),round(reversal,2),round(exhaustion,2),round(confirmation,2),{'CALL':round(call,2),'PUT':round(put,2)},metadata={'fast_momentum_pct':round(fast,4),'slow_momentum_pct':round(slow,4),'channel_high':hi,'channel_low':lo,'phase1_alignment':align,'phase1_quality':quality})

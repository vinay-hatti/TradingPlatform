from .profile import *
from .multi_timeframe import _rows,_atr
class BreakoutIntelligenceEngine:
    def analyze(self,data,supports=None,resistances=None):
        r=_rows(data)
        if len(r)<25:return BreakoutProfile(evidence={'warning':'insufficient history'})
        close=float(r[-1]['close']);prev=float(r[-2]['close']);atr=max(_atr(r),1e-9);vol=float(r[-1].get('volume',0));avg=sum(float(x.get('volume',0)) for x in r[-21:-1])/20;rv=vol/avg if avg else 0
        res=max([x.price for x in (resistances or []) if x.price<=close*1.05] or [max(float(x['high']) for x in r[-21:-1])]); sup=min([x.price for x in (supports or []) if x.price>=close*.95] or [min(float(x['low']) for x in r[-21:-1])])
        up=(close-res)/atr; dn=(sup-close)/atr; state=BreakoutState.NONE.value; conf=0
        if close>res+atr*.1:state=BreakoutState.BREAKOUT_CONFIRMED.value;conf=min(100,55+up*20+(rv-1)*20)
        elif close<sup-atr*.1:state=BreakoutState.BREAKDOWN_CONFIRMED.value;conf=min(100,55+dn*20+(rv-1)*20)
        elif abs(close-res)<=atr*.25:state=BreakoutState.BREAKOUT_SETUP.value;conf=55
        elif abs(close-sup)<=atr*.25:state=BreakoutState.BREAKDOWN_SETUP.value;conf=55
        if prev>res and close<res-atr*.1:state=BreakoutState.FAILED_BREAKOUT.value;conf=75
        if prev<sup and close>sup+atr*.1:state=BreakoutState.FAILED_BREAKDOWN.value;conf=75
        follow=max(0,min(95,conf*.65+min(25,rv*10))); fail=max(5,min(95,100-follow+(20 if rv<.8 else 0)))
        return BreakoutProfile(state,round(conf,2),round(follow,2),round(fail,2),round(max(0,75-abs(close-(res if 'BREAKOUT' in state else sup))/atr*35),2),{'resistance':res,'support':sup,'relative_volume':rv,'atr':atr})

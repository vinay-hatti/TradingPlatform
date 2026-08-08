from .profile import *
from .multi_timeframe import _rows
class ParticipationEngine:
    def analyze(self,data):
        r=_rows(data)
        if len(r)<20:return ParticipationProfile(evidence={'warning':'insufficient history'})
        obv=0.; adl=0.; up=down=0.; vols=[]; mfs=[]
        closes=[]
        for i,x in enumerate(r):
            c=float(x['close']);v=float(x.get('volume',0));h=float(x['high']);l=float(x['low']);closes.append(c);vols.append(v)
            if i: obv += v if c>closes[-2] else -v if c<closes[-2] else 0; up += v if c>closes[-2] else 0; down += v if c<closes[-2] else 0
            mf=((2*c-h-l)/(h-l) if h!=l else 0)*v; adl+=mf;mfs.append(mf)
        avg=sum(vols[-20:])/20; rv=vols[-1]/avg if avg else 0; cmf=sum(mfs[-20:])/max(1e-9,sum(vols[-20:])); price_ret=closes[-1]/closes[-20]-1
        obv_norm=obv/max(1,sum(vols)); score=max(0,min(100,50+obv_norm*80+cmf*80+price_ret*100+(rv-1)*12));
        if rv>2 and price_ret<-.08:state=ParticipationState.CAPITULATION.value
        elif rv>1.8 and price_ret>.06 and down>up:state=ParticipationState.SHORT_COVERING.value
        elif score>=68:state=ParticipationState.ACCUMULATION.value
        elif score<=32:state=ParticipationState.DISTRIBUTION.value
        elif score>=58:state=ParticipationState.RE_ACCUMULATION.value
        elif score<=42:state=ParticipationState.RE_DISTRIBUTION.value
        else:state=ParticipationState.NEUTRAL.value
        deterioration=max(0,min(100,50-score if score<50 else max(0,(1-rv)*30)))
        return ParticipationProfile(state,round(score,2),round(min(100,abs(score-50)*2),2),round(deterioration,2),{'obv_normalized':obv_norm,'adl':adl,'cmf':cmf,'relative_volume':rv,'up_down_volume_ratio':up/max(1,down),'price_return_20':price_ret})

from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from math import erf, exp, log, pi, sqrt
from statistics import mean
from typing import Any, Iterable
from .contracts import DealerPositioningPolicy, ExpirationExposure, HistoricalComparison, InstitutionalMarketStructureSnapshot, IVSurfacePoint, MetricProvenance, StrikeExposure

def _f(v: Any, default: float=0.0) -> float:
    try:
        x=float(v); return x if x==x else default
    except (TypeError,ValueError): return default

def _d(v: Any) -> date|None:
    if isinstance(v,datetime): return v.date()
    if isinstance(v,date): return v
    try: return date.fromisoformat(str(v)[:10])
    except Exception: return None

def _cdf(x: float)->float: return .5*(1+erf(x/sqrt(2)))
def _pdf(x: float)->float: return exp(-.5*x*x)/sqrt(2*pi)
def _clip(x: float,a: float=0,b: float=100)->float: return max(a,min(b,x))

def _greeks(s:float,k:float,t:float,iv:float,r:float,right:str)->tuple[float,float,float,float]:
    if min(s,k,t,iv)<=0: return 0,0,0,0
    rt=sqrt(t); d1=(log(s/k)+(r+.5*iv*iv)*t)/(iv*rt); d2=d1-iv*rt
    delta=_cdf(d1) if right=='CALL' else _cdf(d1)-1
    gamma=_pdf(d1)/(s*iv*rt)
    vanna=(-_pdf(d1)*d2/iv)/100
    next_t=max(t-1/365,1/365); nd1=(log(s/k)+(r+.5*iv*iv)*next_t)/(iv*sqrt(next_t))
    next_delta=_cdf(nd1) if right=='CALL' else _cdf(nd1)-1
    charm=next_delta-delta
    return delta,gamma,vanna,charm

def _sign(right:str, convention:str)->float:
    if convention=='unsigned_market_exposure': return 1.0
    if convention=='customer_long_proxy': return 1.0
    # Public street proxy: dealers assumed short customer calls and puts.
    return -1.0

@dataclass
class _M:
    expiry:date; dte:int; strike:float; right:str; oi:float; volume:float; iv:float; bid:float; ask:float; mid:float; delta:float; gamma:float; vanna:float; charm:float; sign:float; gex:float; dex:float; vex:float; cex:float; premium:float; spread:float|None; trade_ok:bool

class InstitutionalMarketStructureEngine:
    ESTIMATOR_NAME='OI_GREEKS_DEALER_POSITION_PROXY'
    ESTIMATOR_VERSION='44.2.0'
    def __init__(self, policy:DealerPositioningPolicy|None=None): self.policy=policy or DealerPositioningPolicy()

    def analyze(self,symbol:str,as_of:date,spot:float,rows:Iterable[dict[str,Any]],realized_volatility:float|None=None,source_table:str='option_contract_history',previous_snapshot:InstitutionalMarketStructureSnapshot|None=None)->InstitutionalMarketStructureSnapshot:
        data=list(rows); qdates=[x for x in (_d(r.get('quote_date')) for r in data) if x]
        if not qdates: raise ValueError(f'No persisted option snapshot for {symbol} on or before {as_of}')
        snapshot_date=max(qdates)
        # Never mix dates.
        data=[r for r in data if _d(r.get('quote_date'))==snapshot_date]
        metrics=[]; warnings=[]; iv_surface=[]
        quoted=executable=0
        for r in data:
            expiry=_d(r.get('expiry')); strike=_f(r.get('strike')); right=str(r.get('option_type') or '').upper()
            if right in {'C','CALLS'}: right='CALL'
            if right in {'P','PUTS'}: right='PUT'
            if not expiry or strike<=0 or right not in {'CALL','PUT'}: continue
            dte=(expiry-snapshot_date).days; oi=_f(r.get('open_interest')); volume=_f(r.get('volume'))
            if dte<self.policy.minimum_dte or dte>self.policy.maximum_dte or oi<self.policy.minimum_open_interest or volume<self.policy.minimum_volume: continue
            iv=_f(r.get('implied_volatility')); iv=iv/100 if iv>3 else iv
            if iv<=0: continue
            bid_raw=r.get('bid'); ask_raw=r.get('ask'); bid=_f(bid_raw); ask=_f(ask_raw)
            has_quote=bid_raw is not None and ask_raw is not None and bid>=0 and ask>0 and ask>=bid
            if has_quote: quoted+=1
            mid=(bid+ask)/2 if has_quote else max(_f(r.get('last')),0)
            spread=(ask-bid)/mid if has_quote and mid>=self.policy.minimum_midpoint else None
            trade_ok=bool(has_quote and bid>0 and spread is not None and spread<=self.policy.maximum_trade_spread_pct)
            executable+=int(trade_ok)
            t=max(dte/365,1/365); cd,cg,vanna,charm=_greeks(spot,strike,t,iv,self.policy.risk_free_rate,right)
            delta=_f(r.get('delta'),cd) or cd; gamma=_f(r.get('gamma'),cg) or cg; sgn=_sign(right,self.policy.dealer_sign_convention)
            mult=self.policy.contract_multiplier
            unsigned_gex=gamma*oi*mult*spot*spot*.01
            gex=sgn*unsigned_gex; dex=sgn*delta*oi*mult*spot; vex=sgn*vanna*oi*mult*spot; cex=sgn*charm*oi*mult*spot
            premium=mid*volume*mult
            metrics.append(_M(expiry,dte,strike,right,oi,volume,iv,bid,ask,mid,delta,gamma,vanna,charm,sgn,gex,dex,vex,cex,premium,spread,trade_ok))
            if has_quote:
                iv_surface.append(IVSurfacePoint(expiry.isoformat(),dte,strike,right,strike/spot,delta,iv,bid,ask,mid,spread))
        if not metrics: raise ValueError(f'No eligible persisted option contracts for {symbol} on {snapshot_date}')
        age=(as_of-snapshot_date).days
        if age>self.policy.maximum_snapshot_age_days: warnings.append(f'STALE_OPTION_SNAPSHOT:{age}_DAYS')
        if quoted<len(metrics): warnings.append(f'QUOTE_COVERAGE:{quoted}/{len(metrics)}')

        strike_b=defaultdict(lambda:{'call_oi':0.0,'put_oi':0.0,'call_volume':0.0,'put_volume':0.0,'call_gex':0.0,'put_gex':0.0,'gex':0.0,'call_dex':0.0,'put_dex':0.0,'dex':0.0,'vex':0.0,'cex':0.0,'call_spreads':[],'put_spreads':[],'trade_ok':0}); exp_b=defaultdict(lambda:defaultdict(list))
        call_prem=put_prem=0.0
        for m in metrics:
            key=(m.expiry,m.strike); b=strike_b[key]
            b[f'{m.right.lower()}_oi']+=m.oi; b[f'{m.right.lower()}_volume']+=m.volume
            b[f'{m.right.lower()}_gex']+=m.gex; b[f'{m.right.lower()}_dex']+=m.dex
            b['gex']+=m.gex; b['dex']+=m.dex; b['vex']+=m.vex; b['cex']+=m.cex
            if m.spread is not None: b[f'{m.right.lower()}_spreads'].append(m.spread)
            b['trade_ok']+=int(m.trade_ok)
            eb=exp_b[m.expiry]
            for name,val in [('call_oi',m.oi if m.right=='CALL' else 0),('put_oi',m.oi if m.right=='PUT' else 0),('gex',m.gex),('dex',m.dex),('vex',m.vex),('cex',m.cex),('spreads',m.spread if m.spread is not None else None)]:
                if val is not None: eb[name].append(val)
            eb['ivs'].append((abs(m.strike-spot),m.iv)); eb['mids'].append((m.right,m.strike,m.mid))
            call_prem+=m.premium if m.right=='CALL' else 0; put_prem+=m.premium if m.right=='PUT' else 0

        max_oi=max((b['call_oi']+b['put_oi'] for b in strike_b.values()),default=1)
        max_abs_gex=max((abs(b['gex']) for b in strike_b.values()),default=1)
        strikes=[]
        for (expiry,strike),b in sorted(strike_b.items()):
            coi,poi=b['call_oi'],b['put_oi']; oi=coi+poi; prox=max(0,1-abs(strike-spot)/(spot*.15))
            liq=_clip(100*(.45*min(1,oi/max_oi)+.25*prox+.30*(1-min(1,mean(b['call_spreads']+b['put_spreads']) if (b['call_spreads']+b['put_spreads']) else 1))))
            pin=_clip(100*(.55*min(1,oi/max_oi)+.25*prox+.20*min(1,abs(b['gex'])/max_abs_gex)))
            pressure=_clip(50+b['gex']/max_abs_gex*35+b['dex']/(abs(b['dex'])+1)*15)
            strikes.append(StrikeExposure(expiry.isoformat(),(expiry-snapshot_date).days,strike,coi,poi,b['call_volume'],b['put_volume'],b['call_gex'],b['put_gex'],b['gex'],b['call_dex'],b['put_dex'],b['dex'],b['vex'],b['cex'],mean(b['call_spreads']) if b['call_spreads'] else None,mean(b['put_spreads']) if b['put_spreads'] else None,liq,pressure,pin,True,b['trade_ok']>0))

        # Aggregate strike walls across expirations using weighted OI/GEX/proximity/liquidity.
        by_strike=defaultdict(lambda:defaultdict(float))
        for s in strikes:
            z=by_strike[s.strike]
            for n in ('call_open_interest','put_open_interest','call_gamma_exposure','put_gamma_exposure','liquidity_score'): z[n]+=getattr(s,n)
        def wall_scores(side:str):
            oi_key=f'{side}_open_interest'; gx_key=f'{side}_gamma_exposure'; maxoi=max((v[oi_key] for v in by_strike.values()),default=1); maxgx=max((abs(v[gx_key]) for v in by_strike.values()),default=1)
            out=[]
            for k,v in by_strike.items():
                prox=max(0,1-abs(k-spot)/(spot*.20)); score=.55*v[oi_key]/maxoi+.10*abs(v[gx_key])/maxgx+.15*prox+.10*min(1,v['liquidity_score']/1000)+.10*(1/(1+abs(k-spot)/spot))
                out.append((score,k))
            return sorted(out,reverse=True)
        cw=wall_scores('call'); pw=wall_scores('put')
        primary_call=cw[0][1] if cw else None; secondary_call=cw[1][1] if len(cw)>1 else None
        primary_put=pw[0][1] if pw else None; secondary_put=pw[1][1] if len(pw)>1 else None
        magnet=max(strikes,key=lambda s:s.pin_score).strike if strikes else None

        expirations=[]
        for expiry,b in sorted(exp_b.items()):
            mids=b['mids']; nearest=min((abs(k-spot),k) for _,k,_ in mids)[1] if mids else None
            call_mid=sum(mid for rt,k,mid in mids if rt=='CALL' and k==nearest); put_mid=sum(mid for rt,k,mid in mids if rt=='PUT' and k==nearest)
            em=call_mid+put_mid if call_mid>0 and put_mid>0 else None
            spreads=b['spreads']; liq=_clip(100*(1-min(1,mean(spreads) if spreads else 1)))
            expirations.append(ExpirationExposure(expiry.isoformat(),(expiry-snapshot_date).days,sum(b['call_oi']),sum(b['put_oi']),sum(b['gex']),sum(b['dex']),sum(b['vex']),sum(b['cex']),min(b['ivs'])[1] if b['ivs'] else None,em,liq))
        valid_em=[e for e in expirations if self.policy.expected_move_minimum_dte<=e.dte<=self.policy.expected_move_maximum_dte and e.expected_move]
        em_exp=min(valid_em,key=lambda e:abs(e.dte-self.policy.target_dte)) if valid_em else None
        expected_move=em_exp.expected_move if em_exp else None
        atm_iv=em_exp.atm_implied_volatility if em_exp else (min(expirations,key=lambda e:abs(e.dte-self.policy.target_dte)).atm_implied_volatility if expirations else None)
        term_points=[(e.dte,e.atm_implied_volatility) for e in expirations if e.atm_implied_volatility]
        term_slope=self._slope(term_points)
        puts=[m.iv for m in metrics if m.right=='PUT' and -.30<=m.delta<=-.15]; calls=[m.iv for m in metrics if m.right=='CALL' and .15<=m.delta<=.30]; atms=[m.iv for m in metrics if .45<=abs(m.delta)<=.55]
        put_skew=(mean(puts)-mean(atms)) if puts and atms else None; call_skew=(mean(calls)-mean(atms)) if calls and atms else None
        vrp=atm_iv-realized_volatility if atm_iv is not None and realized_volatility is not None else None

        net_gex=sum(m.gex for m in metrics); net_dex=sum(m.dex for m in metrics); net_vex=sum(m.vex for m in metrics); net_cex=sum(m.cex for m in metrics)
        unsigned_gex=sum(abs(m.gex) for m in metrics); unsigned_dex=sum(abs(m.dex) for m in metrics)
        gamma_flip,lower,upper,flip_conf=self._gamma_flip_grid(metrics,spot)
        flip_dist=(spot-gamma_flip)/spot*100 if gamma_flip else None
        regime='POSITIVE_GAMMA' if net_gex>0 else 'NEGATIVE_GAMMA' if net_gex<0 else 'NEUTRAL_GAMMA'
        flow_bias=(call_prem-put_prem)/(call_prem+put_prem) if call_prem+put_prem else 0
        gnorm=net_gex/(unsigned_gex or 1); dnorm=net_dex/(unsigned_dex or 1)
        wall_support=15 if primary_put and primary_put<spot else 0; wall_resist=-10 if primary_call and primary_call<spot*1.01 else 0
        flip_signal=15 if gamma_flip and spot>gamma_flip else -15 if gamma_flip else 0
        gamma_component=50+gnorm*35; delta_component=50+dnorm*30; wall_component=50+wall_support+wall_resist; skew_component=50-_clip((put_skew or 0)*100, -25,25); liquidity_component=100*executable/max(len(metrics),1); activity_component=50+flow_bias*35
        score=_clip(.25*gamma_component+.15*delta_component+.15*(50+flip_signal)+.10*wall_component+.10*(50-(term_slope or 0)*500)+.10*skew_component+.10*liquidity_component+.05*activity_component)
        bull_raw=_clip(50+dnorm*25+flip_signal+wall_support+flow_bias*10); bear_raw=_clip(100-bull_raw); total=bull_raw+bear_raw or 1; bull=100*bull_raw/total; bear=100*bear_raw/total
        range_p=_clip(55+(20 if net_gex>0 else -20)+(10 if magnet and abs(magnet-spot)/spot<.015 else 0)); breakout=_clip(100-range_p+(10 if net_gex<0 else 0)); breakdown=_clip(breakout*(bear/100)); vol_exp=_clip(45+(25 if net_gex<0 else -15)+(10 if term_slope is not None and term_slope<0 else 0)); vol_comp=100-vol_exp
        pin=_clip(max((s.pin_score for s in strikes),default=0)); hedge=_clip(50-gnorm*25+dnorm*20+flow_bias*10)
        conf=_clip(40*min(1,len(metrics)/self.policy.confidence_minimum_rows)+30*min(1,sum(m.oi for m in metrics)/self.policy.confidence_minimum_oi)+20*quoted/max(len(metrics),1)+10*flip_conf)
        if age>self.policy.maximum_snapshot_age_days: conf*=.5
        label='STRONGLY_BULLISH' if score>=75 else 'MODERATELY_BULLISH' if score>=60 else 'NEUTRAL' if score>=40 else 'MODERATELY_BEARISH' if score>=25 else 'STRONGLY_BEARISH'
        comparison=self._comparison(previous_snapshot,snapshot_date,net_gex,net_dex,primary_call,primary_put,gamma_flip,term_slope,put_skew)
        assumptions=(
            'Dealer positioning is estimated from persisted open interest and Greeks; it is not directly reported dealer inventory.',
            'Open interest is positioning stock; volume and midpoint premium are snapshot activity proxies, not aggressor-side trade flow.',
            'Gamma flip is model-derived by repricing aggregate gamma over a spot shock grid.',
            'Vanna and charm are model-derived when direct values are unavailable.',
        )
        provenance=(
            MetricProvenance('open_interest_walls','COMPUTED','POLYGON_OPTION_CHAIN_SNAPSHOT'),
            MetricProvenance('iv_surface','COMPUTED','POLYGON_OPTION_CHAIN_SNAPSHOT'),
            MetricProvenance('gamma_flip','MODEL_DERIVED','PERSISTED_OPTION_SNAPSHOT','BLACK_SCHOLES_SHOCK_GRID',flip_conf),
            MetricProvenance('dealer_exposure','ESTIMATED','PERSISTED_OPTION_SNAPSHOT',self.ESTIMATOR_NAME,conf/100),
            MetricProvenance('snapshot_activity','ESTIMATED','PERSISTED_OPTION_SNAPSHOT','SNAPSHOT_ACTIVITY_PROXY',quoted/max(len(metrics),1)),
        )
        return InstitutionalMarketStructureSnapshot(symbol.upper(),as_of.isoformat(),snapshot_date.isoformat(),spot,source_table,len(metrics),executable,100*quoted/max(len(metrics),1),self.policy.dealer_sign_convention,self.ESTIMATOR_NAME,self.ESTIMATOR_VERSION,unsigned_gex,unsigned_dex,net_gex,net_dex,net_vex,net_cex,regime,gamma_flip,flip_dist,lower,upper,flip_conf,primary_call,secondary_call,primary_put,secondary_put,magnet,primary_put,primary_call,expected_move,expected_move/spot*100 if expected_move else None,spot+expected_move if expected_move else None,spot-expected_move if expected_move else None,atm_iv,term_slope,put_skew,call_skew,vrp,call_prem,put_prem,hedge,score,label,bull,bear,range_p,breakout,breakdown,vol_exp,vol_comp,pin,'HIGH' if conf>=80 else 'MEDIUM' if conf>=55 else 'LOW',conf,assumptions,tuple(warnings),provenance,comparison,tuple(strikes),tuple(expirations),tuple(iv_surface))

    def _gamma_flip_grid(self,metrics:list[_M],spot:float):
        pts=[]
        for i in range(self.policy.gamma_grid_steps):
            s=spot*(self.policy.gamma_grid_min_factor+(self.policy.gamma_grid_max_factor-self.policy.gamma_grid_min_factor)*i/(self.policy.gamma_grid_steps-1))
            total=0.0
            for m in metrics:
                _,g,_,_=_greeks(s,m.strike,max(m.dte/365,1/365),m.iv,self.policy.risk_free_rate,m.right)
                total+=m.sign*g*m.oi*self.policy.contract_multiplier*s*s*.01
            pts.append((s,total))
        for (s1,g1),(s2,g2) in zip(pts,pts[1:]):
            if g1==0: return s1,s1,s1,1.0
            if g1*g2<0:
                flip=s1+(s2-s1)*abs(g1)/(abs(g1)+abs(g2)); spacing=(s2-s1)/spot
                return flip,s1,s2,_clip(1-spacing*10,0,1)
        return None,None,None,0.0
    @staticmethod
    def _slope(points):
        if len(points)<2:return None
        xs=[float(x) for x,_ in points]; ys=[float(y) for _,y in points]; mx,my=mean(xs),mean(ys); den=sum((x-mx)**2 for x in xs)
        return None if not den else sum((x-mx)*(y-my) for x,y in zip(xs,ys))/den
    @staticmethod
    def _comparison(prev,dt,gex,dex,cw,pw,flip,term,skew):
        if not prev:return HistoricalComparison()
        def diff(a,b): return None if a is None or b is None else a-b
        return HistoricalComparison(prev.option_snapshot_date,None,gex-prev.net_gamma_exposure,dex-prev.net_delta_exposure,diff(cw,prev.primary_call_wall),diff(pw,prev.primary_put_wall),diff(flip,prev.gamma_flip),diff(term,prev.iv_term_slope),diff(skew,prev.put_skew))

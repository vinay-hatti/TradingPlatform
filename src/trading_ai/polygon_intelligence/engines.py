from __future__ import annotations
from dataclasses import dataclass
from math import sqrt
from statistics import mean
from typing import Iterable, Mapping, Any
from .contracts import InstitutionalMarketContext, MarketContextEvaluation

def clamp(v: float, lo: float=0.0, hi: float=100.0) -> float: return max(lo,min(hi,float(v)))

class HistoricalVolatilityEngine:
    """Polygon-derived volatility statistics without look-ahead."""
    @staticmethod
    def iv_rank(current: float, history: Iterable[float], minimum_observations: int=20) -> dict[str, Any]:
        xs=[float(x) for x in history if x is not None and float(x)>0]
        if len(xs)<minimum_observations:
            return {'value':None,'status':'INSUFFICIENT_HISTORY','observation_count':len(xs),'confidence':clamp(len(xs)/minimum_observations*60)}
        lo,hi=min(xs),max(xs)
        value=50.0 if hi==lo else clamp((float(current)-lo)/(hi-lo)*100)
        return {'value':round(value,4),'status':'READY','observation_count':len(xs),'confidence':clamp(60+min(len(xs),252)/252*40)}
    @staticmethod
    def iv_percentile(current: float, history: Iterable[float], minimum_observations: int=20) -> dict[str, Any]:
        xs=[float(x) for x in history if x is not None and float(x)>0]
        if len(xs)<minimum_observations:
            return {'value':None,'status':'INSUFFICIENT_HISTORY','observation_count':len(xs),'confidence':clamp(len(xs)/minimum_observations*60)}
        return {'value':round(sum(x<float(current) for x in xs)/len(xs)*100,4),'status':'READY','observation_count':len(xs),'confidence':clamp(60+min(len(xs),252)/252*40)}
    @staticmethod
    def realized_volatility(returns: Iterable[float], annualization: int=252) -> float | None:
        xs=[float(x) for x in returns if x is not None]
        if len(xs)<2:return None
        m=mean(xs); variance=sum((x-m)**2 for x in xs)/(len(xs)-1)
        return sqrt(variance*annualization)
    @classmethod
    def strategy_fit(cls, iv_rank: float|None, iv_percentile: float|None, vrp: float|None, liquidity_score: float=50) -> str:
        if liquidity_score<30:return 'NEUTRAL'
        score=mean([x for x in (iv_rank,iv_percentile) if x is not None] or [50])
        if vrp is not None: score += max(-20,min(20,vrp*100))
        if score>=75:return 'SHORT_PREMIUM_FAVORABLE'
        if score>=60:return 'SHORT_PREMIUM_SELECTIVE'
        if score<=25:return 'LONG_PREMIUM_FAVORABLE'
        if score<=40:return 'LONG_PREMIUM_SELECTIVE'
        return 'NEUTRAL'

class MicrostructureLiquidityEngine:
    """Computes only metrics supportable by Polygon trades/NBBO; depth stays unavailable."""
    @staticmethod
    def snapshot_metrics(quotes: Iterable[Mapping[str,Any]], trades: Iterable[Mapping[str,Any]]=()) -> dict[str,Any]:
        q=list(quotes); t=list(trades)
        valid=[x for x in q if (x.get('bid') or 0)>0 and (x.get('ask') or 0)>0 and x.get('ask')>=x.get('bid')]
        rel=[]
        for x in valid:
            mid=(float(x['bid'])+float(x['ask']))/2
            if mid>0: rel.append((float(x['ask'])-float(x['bid']))/mid)
        sizes=[float(x.get('size') or 0) for x in t if float(x.get('size') or 0)>0]
        coverage=len(valid)/len(q)*100 if q else 0.0
        spread=mean(rel)*100 if rel else None
        avg_size=mean(sizes) if sizes else None
        score=clamp(coverage-(spread or 10)*3 + min(avg_size or 0,100)/5)
        regime='DEEP' if score>=80 else 'NORMAL' if score>=60 else 'THIN' if score>=40 else 'FRAGMENTED' if score>=20 else 'STRESSED'
        return {'quote_count':len(q),'trade_count':len(t),'executable_quote_pct':round(coverage,4),'median_relative_spread_pct':None if spread is None else round(spread,4),'average_trade_size':None if avg_size is None else round(avg_size,4),'liquidity_score':round(score,4),'liquidity_regime':regime,'depth_available':False,'depth_status':'CAPABILITY_UNAVAILABLE','provenance':'POLYGON_TRADES_NBBO'}

class InstitutionalMarketIntelligencePolicy:
    def evaluate(self, context: InstitutionalMarketContext|None, *, direction: str, strategy_family: str) -> MarketContextEvaluation:
        if context is None or context.freshness_status in {'UNAVAILABLE','MISSING'}:
            return MarketContextEvaluation('UNAVAILABLE',True,0.0,reasons=('MARKET_CONTEXT_UNAVAILABLE_NEUTRAL_FALLBACK',),confidence=0.0,context=context or InstitutionalMarketContext())
        d=direction.upper(); s=strategy_family.upper(); reasons=[]; conflicts=[]
        bullish=d in {'CALL','BULLISH','LONG','BUY'}; bearish=d in {'PUT','BEARISH','SHORT','SELL'}
        market=(context.market_sentiment_score-50)/10
        sector=(context.sector_breadth_score-50)/12
        if bearish: market,sector=-market,-sector
        if not bullish and not bearish: market=sector=0
        vol=0.0
        fit=context.strategy_fit.upper()
        if 'LONG_PREMIUM' in s: vol=3 if fit=='LONG_PREMIUM_FAVORABLE' else 1 if fit=='LONG_PREMIUM_SELECTIVE' else -3 if fit.startswith('SHORT_PREMIUM') else 0
        elif 'SHORT_PREMIUM' in s or any(x in s for x in ('CONDOR','CREDIT')): vol=3 if fit=='SHORT_PREMIUM_FAVORABLE' else 1 if fit=='SHORT_PREMIUM_SELECTIVE' else -3 if fit.startswith('LONG_PREMIUM') else 0
        dealer=((context.dealer_positioning_score-50)/15) * (-1 if bearish else 1)
        liquidity=(50-context.market_risk_score)/25 if context.liquidity_regime not in {'STRESSED','FRAGMENTED'} else -4
        risk=-(context.market_risk_score-50)/10
        confidence=(context.confidence-50)/25
        total=max(-15,min(15,market+sector+vol+dealer+liquidity+risk+confidence))
        if market>1:reasons.append('MARKET_ALIGNED')
        elif market<-1:conflicts.append('MARKET_CONFLICT')
        if sector>1:reasons.append('SECTOR_ALIGNED')
        elif sector<-1:conflicts.append('SECTOR_CONFLICT')
        if vol>0:reasons.append('VOLATILITY_STRATEGY_FIT')
        elif vol<0:conflicts.append('VOLATILITY_STRATEGY_CONFLICT')
        allowed=not (context.liquidity_regime=='STRESSED' and context.market_risk_score>=85)
        outcome='SUPPORTIVE' if total>=5 else 'CONDITIONALLY_SUPPORTIVE' if total>=2 else 'NEUTRAL' if total>-2 else 'CONFLICTED' if total>-6 else 'UNSUPPORTIVE'
        return MarketContextEvaluation(outcome,allowed,round(total,4),round(market,4),round(sector,4),round(vol,4),round(dealer,4),round(liquidity,4),round(risk,4),round(confidence,4),tuple(reasons),tuple(conflicts),context.confidence,context)

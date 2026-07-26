from __future__ import annotations
from typing import Any

def intelligence_adjustments(context:dict[str,Any],sector:str,direction:str,strategy_family:str='LONG_PREMIUM',max_sector:float=6,max_risk:float=6)->dict[str,Any]:
    if not context:return {'sector_score_adjustment':0.0,'risk_score_adjustment':0.0,'reasons':['Market intelligence snapshot unavailable.']}
    reasons=[]; direction=direction.upper(); sec=(context.get('sector_context') or {}).get(sector,{})
    breadth=float(sec.get('breadth_score',50)); momentum=float(sec.get('momentum_score',50)); raw=((breadth-50)/12+(momentum-50)/15)*(1 if direction=='CALL' else -1)
    sector_adj=max(-max_sector,min(max_sector,raw))
    if abs(sector_adj)>=.5:reasons.append(f"{sector} constituent breadth and momentum contribute {sector_adj:+.2f}.")
    risk=float(context.get('market_risk_score',50)); risk_adj=max(-max_risk,min(0,-max(0,risk-45)/8))
    if risk_adj<-.25:reasons.append(f"Market risk score {risk:.1f} reduces conviction by {abs(risk_adj):.2f}.")
    corr=str(context.get('correlation_regime','UNKNOWN'))
    if corr in {'HIGH_CORRELATION','PANIC_CORRELATION'}:risk_adj=max(-max_risk,risk_adj-1);reasons.append(f'{corr} increases concentration risk.')
    return {'sector_score_adjustment':round(sector_adj,2),'risk_score_adjustment':round(risk_adj,2),'market_intelligence_status':context.get('status','FRESH'),'market_sentiment_score':context.get('sentiment_score',50),'market_risk_score':risk,'correlation_regime':corr,'sector_breadth_score':breadth,'sector_rotation_label':sec.get('rotation_label','UNKNOWN'),'market_intelligence_reasons':reasons}

from __future__ import annotations
from typing import Any

def market_score_adjustment(context:dict[str,Any], direction:str, strategy_family:str='LONG_PREMIUM', maximum_adjustment:float=8.0)->tuple[float,list[str]]:
    direction=direction.upper(); strategy=strategy_family.upper(); reasons=[]; raw=0.0
    bias=str(context.get('market_bias','NEUTRAL'))
    trend=float(context.get('trend_score',50)); breadth=float(context.get('breadth_score',50))
    if direction=='CALL': raw+=(trend-50)/12+(breadth-50)/18
    elif direction=='PUT': raw-=(trend-50)/12+(breadth-50)/18
    if ('BULLISH' in bias and direction=='CALL') or ('BEARISH' in bias and direction=='PUT'): raw+=2; reasons.append(f'{bias} market bias aligns with {direction}.')
    if ('BULLISH' in bias and direction=='PUT') or ('BEARISH' in bias and direction=='CALL'): raw-=2; reasons.append(f'{bias} market bias conflicts with {direction}.')
    vol=str(context.get('volatility_regime','NORMAL'))
    if 'LONG_PREMIUM' in strategy and vol=='COMPRESSED': raw-=1.5; reasons.append('Compressed volatility reduces immediate long-premium velocity.')
    if 'LONG_PREMIUM' in strategy and vol=='EXPANDING': raw+=1.5; reasons.append('Expanding volatility supports long-premium structures.')
    if context.get('regime_transition_risk')=='HIGH': raw-=1.5; reasons.append('High regime-transition risk reduces conviction.')
    adjustment=max(-maximum_adjustment,min(maximum_adjustment,raw))
    return round(adjustment,2),reasons

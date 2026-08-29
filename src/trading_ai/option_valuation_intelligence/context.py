from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from math import sqrt
from statistics import median, pstdev
from typing import Any

from .engine import clamp, deep_get, extract_legs, num, weighted_leg_value


def dte_bucket(dte: float) -> str:
    d=int(max(0,dte))
    if d <= 7:return '0-7'
    if d <= 30:return '8-30'
    if d <= 60:return '31-60'
    if d <= 120:return '61-120'
    return '121+'


def moneyness_bucket(spot: float, strike: float, right: str) -> str:
    if spot <= 0 or strike <= 0:return 'UNKNOWN'
    pct=(strike/spot-1)*100
    if right.upper().startswith('P'):pct=-pct
    if pct <= -10:return 'DEEP_ITM'
    if pct <= -3:return 'ITM'
    if pct < 3:return 'ATM'
    if pct < 10:return 'OTM'
    return 'DEEP_OTM'


def contract_features(
    row,
    symbol: str,
    sector: str,
    spot: float,
    *,
    payload_override: dict[str, Any] | None = None,
) -> dict[str,Any]:
    payload=dict(payload_override if payload_override is not None else (row.payload_json or {}))
    legs=extract_legs(payload)
    iv,_=weighted_leg_value(legs,'implied_volatility','iv')
    if iv is None: iv=num(payload.get('implied_volatility') or payload.get('iv'))
    leg_dtes=[num(leg.get('dte')) for leg in legs if num(leg.get('dte'))>0]
    dte=min(leg_dtes) if leg_dtes else num(payload.get('dte') or payload.get('days_to_expiration'),45)
    representative=next((leg for leg in legs if str(leg.get('side','BUY')).upper()=='BUY'),legs[0] if legs else {})
    strike=num(representative.get('strike') or representative.get('strike_price'),spot)
    right=str(representative.get('right') or representative.get('option_type') or 'C').upper()[:1]
    strategy=str(payload.get('strategy') or payload.get('strategy_name') or payload.get('strategy_type') or 'UNKNOWN').upper()
    liquidity=num(getattr(row,'liquidity_score',None),50)
    return {
        'contract_recommendation_id':row.contract_recommendation_id,'symbol':symbol,'sector':sector or 'UNKNOWN',
        'spot':spot,'iv':float(iv or 0),'dte':dte,'dte_bucket':dte_bucket(dte),'strike':strike,'right':right,
        'moneyness_bucket':moneyness_bucket(spot,strike,right),'strategy':strategy,'liquidity':liquidity,
        'peer_group':f'{sector or "UNKNOWN"}|{right}|{dte_bucket(dte)}|{moneyness_bucket(spot,strike,right)}',
    }


def build_relative_context(features: list[dict]) -> dict[str,dict]:
    groups=defaultdict(list)
    for f in features:
        if f['iv']>0: groups[f['peer_group']].append(f)
    out={}
    for group,items in groups.items():
        values=[x['iv'] for x in items]
        med=median(values); sd=pstdev(values) if len(values)>1 else 0.0
        symbols=len(set(x['symbol'] for x in items))
        for f in items:
            peers=[x['iv'] for x in items if x['symbol'] != f['symbol']]
            peer_med=median(peers) if peers else med
            z=(f['iv']-peer_med)/sd if sd>1e-9 else 0.0
            divergence=(peer_med-f['iv'])/max(f['iv'],.01)*100
            regime='DISCOUNTED_TO_PEERS' if z<=-1 else ('RICH_TO_PEERS' if z>=1 else 'IN_LINE')
            out[f['contract_recommendation_id']]={
                'available':len(peers)>=2 and symbols>=2,'peer_group':group,'peer_median_iv':peer_med,
                'symbol_iv':f['iv'],'divergence_pct':divergence,'z_score':z,'peer_count':len(peers),
                'symbol_count':symbols,'relationship_regime':regime,'quality':'CROSS_SECTIONAL_GOVERNED' if len(peers)>=2 else 'INSUFFICIENT_PEERS',
            }
    return out


def _parse_date(v) -> date|None:
    if isinstance(v,date):return v
    if not v:return None
    try:return datetime.fromisoformat(str(v).replace('Z','+00:00')).date()
    except ValueError:
        try:return date.fromisoformat(str(v)[:10])
        except ValueError:return None


def event_context(symbol: str, opportunity: dict, events: list, iv: float, as_of: date|None=None) -> dict:
    as_of=as_of or date.today()
    candidates=[]
    # Governed persisted events.
    for e in events:
        if str(e.status).upper()!='ACTIVE' or str(e.symbol).upper() not in {'*','ALL',symbol.upper()}:continue
        ed=_parse_date(e.event_date)
        if not ed:continue
        days=(ed-as_of).days
        if -1 <= days <= 45:candidates.append((abs(days),days,e.event_type,ed,e.expected_move_pct,e.historical_move_pct,e.confidence,e.source,e.event_id))
    # Existing opportunity payload can provide a governed upstream event without duplicating it.
    for key,etype in [('next_earnings_date','EARNINGS'),('earnings_date','EARNINGS'),('event_date','CORPORATE_EVENT')]:
        ed=_parse_date(deep_get(opportunity,key))
        if ed:
            days=(ed-as_of).days
            if -1<=days<=45:
                candidates.append((abs(days),days,etype,ed,deep_get(opportunity,'expected_event_move_pct'),deep_get(opportunity,'historical_event_move_pct'),deep_get(opportunity,'event_confidence') or 60,'UPSTREAM_OPPORTUNITY',f'UPSTREAM-{symbol}-{ed}'))
    if not candidates:
        return {'available':False,'quality':'NO_EVENT_CONTEXT','score':50.0,'event_type':None,'days_to_event':None}
    _,days,etype,ed,expected,historical,confidence,source,event_id=sorted(candidates,key=lambda x:x[0])[0]
    expected=num(expected,num(historical,0.0))
    horizon=max(1,days if days>=0 else 1)
    implied=max(.1,iv*sqrt(horizon/365.0)*100)
    available_expected=expected>0
    score=clamp(50 + ((expected-implied)/implied*35 if available_expected else 0))
    return {
        'available':True,'quality':'GOVERNED_EVENT_MODEL' if available_expected else 'EVENT_IDENTIFIED_NO_MOVE_MODEL',
        'score':score,'event_id':event_id,'event_type':etype,'event_date':ed.isoformat(),'days_to_event':days,
        'implied_move_pct':implied,'expected_move_pct':expected if available_expected else None,
        'historical_move_pct':num(historical) or None,'confidence':num(confidence,50),'source':source,
        'edge_pct':((expected-implied)/implied*100) if available_expected else 0.0,
    }

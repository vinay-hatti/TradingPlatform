from __future__ import annotations
from datetime import date
from math import sqrt
from sqlalchemy import text

def _mid(r):
    m=r.get('mid')
    if m and float(m)>0:return float(m)
    b=float(r.get('bid') or 0);a=float(r.get('ask') or 0)
    return (a+b)/2 if a>0 and b>=0 and a>=b else 0

def _atm_pair(rows,spot):
    calls=[r for r in rows if str(r['option_type']).upper().startswith('C')]
    puts=[r for r in rows if str(r['option_type']).upper().startswith('P')]
    if not calls or not puts:return None
    strikes=sorted(set(float(r['strike']) for r in rows))
    strike=min(strikes,key=lambda x:abs(x-spot))
    c=min(calls,key=lambda r:abs(float(r['strike'])-strike));p=min(puts,key=lambda r:abs(float(r['strike'])-strike))
    return c,p,strike

def _atm_metrics(session,symbol,quote_date,expiry,spot):
    rows=session.execute(text("""SELECT option_type,strike,bid,ask,mid,implied_volatility,volume,open_interest
      FROM option_contract_history WHERE UPPER(underlying_symbol)=:s AND quote_date=:q AND expiry=:e
      ORDER BY ABS(strike-:p) LIMIT 40"""),{'s':symbol.upper(),'q':quote_date,'e':expiry,'p':spot}).mappings().all()
    pair=_atm_pair(rows,spot)
    if not pair:return None
    c,p,strike=pair;cm,pm=_mid(c),_mid(p)
    if cm<=0 or pm<=0:return None
    spreads=[]
    for r,m in ((c,cm),(p,pm)):
        b=float(r.get('bid') or 0);a=float(r.get('ask') or 0)
        spreads.append((a-b)/m if a>=b and m>0 else 9)
    ivs=[float(r.get('implied_volatility') or 0) for r in (c,p) if float(r.get('implied_volatility') or 0)>0]
    iv=sum(ivs)/len(ivs) if ivs else None
    liq=min(100.0,(float(c.get('open_interest') or 0)+float(p.get('open_interest') or 0))/20+(float(c.get('volume') or 0)+float(p.get('volume') or 0))/10)
    return {'expiry':expiry,'strike':strike,'straddle_pct':(cm+pm)/spot*100,'iv':iv,'spread_pct':sum(spreads)/2,'liquidity_score':liq}

class GovernedImpliedMoveResolver:
    def resolve(self,session,*,symbol,event_date):
        symbol='SPY' if symbol.upper() in ('*','ALL') else symbol.upper()
        q=session.execute(text("SELECT MAX(quote_date) FROM option_contract_history WHERE UPPER(underlying_symbol)=:s"),{'s':symbol}).scalar()
        if not q:return None,None,0,{'reason':'NO_OPTIONS'}
        spot=session.execute(text("SELECT close FROM price_history WHERE UPPER(symbol)=:s AND date<=:d ORDER BY date DESC LIMIT 1"),{'s':symbol,'d':q}).scalar()
        if not spot:return None,str(q),0,{'reason':'NO_SPOT'}
        expiries=[r[0] for r in session.execute(text("SELECT DISTINCT expiry FROM option_contract_history WHERE UPPER(underlying_symbol)=:s AND quote_date=:q ORDER BY expiry"),{'s':symbol,'q':q}).all()]
        before=[x for x in expiries if x<event_date];after=[x for x in expiries if x>=event_date]
        if not after:return None,str(q),0,{'reason':'NO_EVENT_EXPIRY'}
        post=_atm_metrics(session,symbol,q,after[0],float(spot))
        if not post:return None,str(q),0,{'reason':'NO_ATM_PAIR'}
        reasons=[];method='TIME_ADJUSTED_ATM_STRADDLE';raw=post['straddle_pct'];estimate=raw
        if before and post.get('iv'):
            pre=_atm_metrics(session,symbol,q,before[-1],float(spot))
            if pre and pre.get('iv'):
                t1=max(1,(pre['expiry']-q).days)/365;t2=max(1,(post['expiry']-q).days)/365
                base_var=pre['iv']**2*t1
                ordinary_rate=base_var/t1
                ordinary_post=ordinary_rate*t2
                event_var=max(0,post['iv']**2*t2-ordinary_post)
                isolated=sqrt(event_var)*100
                if isolated>0:
                    estimate=isolated;method='TERM_VARIANCE_ISOLATION'
        if method!='TERM_VARIANCE_ISOLATION':
            # Deduct ordinary move estimated from 20-session realized volatility.
            closes=[float(r[0]) for r in session.execute(text("SELECT close FROM price_history WHERE UPPER(symbol)=:s AND date<=:q ORDER BY date DESC LIMIT 21"),{'s':symbol,'q':q}).all()]
            if len(closes)>=10:
                rets=[(closes[i-1]/closes[i]-1) for i in range(1,len(closes)) if closes[i]]
                if rets:
                    mu=sum(rets)/len(rets);rv=sqrt(sum((x-mu)**2 for x in rets)/max(1,len(rets)-1))*sqrt(max(1,(post['expiry']-q).days))*100
                    estimate=sqrt(max(0,raw**2-rv**2)) or raw
        if post['spread_pct']>0.35: reasons.append('WIDE_ATM_SPREAD')
        if post['liquidity_score']<10: reasons.append('LOW_LIQUIDITY')
        if estimate>max(25,raw*1.75): reasons.append('MOVE_TO_STRADDLE_OUTLIER')
        governed=estimate
        status='ACCEPTED'
        if 'MOVE_TO_STRADDLE_OUTLIER' in reasons:
            governed=min(estimate,raw*1.5);status='CAPPED'
        if post['spread_pct']>0.75:
            return None,str(q),post['liquidity_score'],{'reason':'QUOTE_QUALITY_REJECTED','raw_straddle_move_pct':raw,'spread_pct':post['spread_pct'],'outlier_reasons':reasons}
        return round(governed,4),str(q),post['liquidity_score'],{'method':method,'expiry':str(post['expiry']),'raw_straddle_move_pct':raw,'isolated_event_move_pct':estimate if method=='TERM_VARIANCE_ISOLATION' else None,'quote_quality_score':round(max(0,100-post['spread_pct']*100),2),'surface_quality_score':80 if method=='TERM_VARIANCE_ISOLATION' else 45,'outlier_status':status,'outlier_reasons':reasons,'governed_move_pct':governed}

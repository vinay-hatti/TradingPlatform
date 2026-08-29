from __future__ import annotations
import argparse, hashlib, json
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text
from trading_ai.database.session import SessionLocal
from trading_ai.historical_underlying_replay.regime import HistoricalRegimeAuthorityService

VERSION='M77.6-LIVE-FORWARD-SHADOW-1.0'
START=date(2026,8,18)
POLICY=Path('reports/m77/m77_5_research_shadow_policy.json')
CERT=Path('reports/m77/m77_5_shadow_policy_certification.json')

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def band(v):
    for a,b in zip((0,40,50,60,70,80,90),(40,50,60,70,80,90,101)):
        if a<=v<b:return f'[{a},{b})'
    return '[OUT_OF_RANGE]'
def split_id(x):
    c,h=x.rsplit('@@',1); return c,int(h[:-1])
def ids(d,c,s,score,r):
    b=band(score)
    return {f'direction::direction={d}',f'direction_regime::direction={d}|historical_regime={r}',f'direction_category::direction={d}|primary_category={c}',f'direction_structure::direction={d}|structure={s}',f'direction_category_score::direction={d}|primary_category={c}|score_band={b}',f'direction_category_structure::direction={d}|primary_category={c}|structure={s}',f'direction_score_regime::direction={d}|historical_regime={r}|score_band={b}'}

def load_policy():
    p=json.loads(POLICY.read_text()); c=json.loads(CERT.read_text())
    if p.get('mode')!='RESEARCH_SHADOW_ONLY' or p.get('production_champion_change') is not False: raise RuntimeError('M77.5 policy not frozen')
    for k in ('score_mutation','threshold_mutation','weight_mutation','decision_mutation'):
        if p.get(k)!='NONE': raise RuntimeError(f'M77.5 mutation enabled: {k}')
    if p.get('bearish_policy')!='ABSTAIN_FROM_BEARISH_CHALLENGER_SUPPORT_DO_NOT_INVERT': raise RuntimeError('bearish policy changed')
    return p,c,sha(POLICY)

def latest(session):
    r=session.execute(text("SELECT scanner_run_id,status,snapshot_timestamp,payload_json FROM stock_scanner_publications WHERE publication_name='current_stock_intelligence' AND status IN ('READY','DEGRADED') ORDER BY snapshot_timestamp DESC LIMIT 1")).mappings().first()
    if not r: raise RuntimeError('No current_stock_intelligence publication')
    p=dict(r['payload_json'] or {}); lin=dict(p.get('lineage') or {}); raw=lin.get('market_as_of_date') or lin.get('source_as_of_date') or str(r['snapshot_timestamp'])[:10]
    return dict(r),date.fromisoformat(str(raw)[:10])
def fields(r):
    p=dict(r['payload_json'] or {}); sc=dict(p.get('scores') or {})
    return p,str(p.get('direction') or 'UNKNOWN').upper(),str(sc.get('primary_category') or r.get('category') or 'UNKNOWN').upper(),str(p.get('structure') or 'UNKNOWN').upper(),float(sc.get('overall') if sc.get('overall') is not None else r.get('score') or 0),float(p.get('confidence') if p.get('confidence') is not None else sc.get('confidence') or 0),p.get('state_hash')

def capture(session):
    policy,cert,ph=load_policy(); pub,asof=latest(session)
    if asof<START: raise RuntimeError(f'Prospective capture cannot predate {START}; got {asof}')
    regime_map=HistoricalRegimeAuthorityService(session).build_authority([asof]); snap=regime_map.get(asof); regime=snap.regime if snap else 'UNKNOWN'
    certified=set(policy.get('shadow_policy_certified_candidate_horizon_ids') or []); tier1=set(policy.get('full_year_depth_preferred_candidate_horizon_ids') or [])
    watch={x['candidate_horizon_id'] for x in cert.get('certification',[]) if x.get('status')=='WALK_FORWARD_SUPPORTED_NOT_SHADOW_CERTIFIED'}
    rows=[dict(x) for x in session.execute(text('SELECT id,candidate_id,symbol,score,category,snapshot_timestamp,payload_json FROM stock_scanner_candidates WHERE scanner_run_id=:r ORDER BY symbol,score DESC'),{'r':pub['scanner_run_id']}).mappings()]
    symbols=sorted({x['symbol'] for x in rows}); prices={x['symbol']:(x['date'],float(x['close'])) for x in session.execute(text('SELECT DISTINCT ON (symbol) symbol,date,close FROM price_history WHERE symbol=ANY(:s) AND date<=:d AND close>0 ORDER BY symbol,date DESC'),{'s':symbols,'d':asof}).mappings()}
    ins=dup=0; tiers={k:0 for k in ('SHADOW_CERTIFIED_TIER_1','SHADOW_CERTIFIED_TIER_2','SHADOW_WATCH_SAMPLE')}; matched=set()
    for r in rows:
        p,d,c,st,score,conf,state=fields(r); pi=prices.get(r['symbol'])
        if d not in {'BULLISH','STRONG_BULLISH'} or not pi or pi[0]!=asof: continue
        possible=ids(d,c,st,score,regime)
        for full in certified|watch:
            cid,h=split_id(full)
            if cid not in possible: continue
            tier='SHADOW_CERTIFIED_TIER_1' if full in tier1 else 'SHADOW_CERTIFIED_TIER_2' if full in certified else 'SHADOW_WATCH_SAMPLE'
            fp=hashlib.sha256(f'{VERSION}|{asof}|{r["symbol"]}|{full}|{ph}'.encode()).hexdigest()
            if session.execute(text('SELECT 1 FROM m77_shadow_signals WHERE signal_fingerprint=:f'),{'f':fp}).first(): dup+=1; continue
            session.execute(text('INSERT INTO m77_shadow_signals(signal_id,signal_fingerprint,captured_at,source_as_of_date,scanner_run_id,candidate_id,symbol,direction,primary_category,structure,overall_score,confidence,historical_regime,shadow_tier,candidate_horizon_id,horizon_sessions,reference_price,state_hash,policy_sha256,status,payload_json) VALUES(:id,:fp,:now,:d,:run,:cid,:sym,:dir,:cat,:st,:score,:conf,:reg,:tier,:cohort,:h,:px,:state,:sha,\'OPEN\',CAST(:payload AS jsonb))'),{'id':'m77-shadow-'+uuid4().hex,'fp':fp,'now':datetime.now(timezone.utc),'d':asof,'run':pub['scanner_run_id'],'cid':r.get('candidate_id') or r['id'],'sym':r['symbol'],'dir':d,'cat':c,'st':st,'score':score,'conf':conf,'reg':regime,'tier':tier,'cohort':full,'h':h,'px':pi[1],'state':state,'sha':ph,'payload':json.dumps({'version':VERSION,'production_effect':False,'publication_snapshot_timestamp':pub['snapshot_timestamp'],'regime_authority':snap.as_dict() if snap else None}, default=str)})
            ins+=1;tiers[tier]+=1;matched.add(r['symbol'])
    session.commit(); return {'version':VERSION,'status':'READY','mode':'PROSPECTIVE_RESEARCH_SHADOW_CAPTURE','source_as_of_date':str(asof),'scanner_run_id':pub['scanner_run_id'],'candidate_count':len(rows),'regime':regime,'matched_symbols':len(matched),'signals_inserted':ins,'idempotent_duplicates':dup,'by_tier':tiers,'policy_sha256':ph,'production_authority_effect':False}

def mature(session):
    sig=[dict(x) for x in session.execute(text("SELECT signal_id,symbol,source_as_of_date,direction,horizon_sessions,reference_price,candidate_horizon_id,shadow_tier FROM m77_shadow_signals WHERE status='OPEN' ORDER BY source_as_of_date,symbol")).mappings()]
    matured=waiting=0
    for s in sig:
        dates=list(session.execute(text("SELECT date FROM price_history WHERE symbol='SPY' AND date>:d GROUP BY date ORDER BY date LIMIT :n"),{'d':s['source_as_of_date'],'n':s['horizon_sessions']}).scalars())
        if len(dates)<s['horizon_sessions']: waiting+=1;continue
        td=dates[-1]; close=session.execute(text('SELECT close FROM price_history WHERE symbol=:s AND date=:d AND close>0 LIMIT 1'),{'s':s['symbol'],'d':td}).scalar()
        if close is None: waiting+=1;continue
        raw=(float(close)/float(s['reference_price'])-1)*100; thesis=raw if s['direction'] in {'BULLISH','STRONG_BULLISH'} else -raw
        session.execute(text('INSERT INTO m77_shadow_outcomes(outcome_id,signal_id,target_session_date,observed_at,target_close,raw_return_pct,thesis_return_pct,directional_hit,payload_json) VALUES(:id,:sid,:td,:now,:close,:raw,:thesis,:hit,CAST(:p AS jsonb)) ON CONFLICT(signal_id) DO NOTHING'),{'id':'m77-outcome-'+uuid4().hex,'sid':s['signal_id'],'td':td,'now':datetime.now(timezone.utc),'close':float(close),'raw':raw,'thesis':thesis,'hit':thesis>0,'p':json.dumps({'version':VERSION,'production_effect':False})})
        session.execute(text("UPDATE m77_shadow_signals SET status='MATURED' WHERE signal_id=:id"),{'id':s['signal_id']});matured+=1
    session.commit(); return {'version':VERSION,'status':'READY','open_examined':len(sig),'matured':matured,'waiting':waiting,'production_authority_effect':False}

def report(session):
    counts=[dict(x) for x in session.execute(text('SELECT shadow_tier,status,horizon_sessions,COUNT(*) n FROM m77_shadow_signals GROUP BY 1,2,3 ORDER BY 1,3,2')).mappings()]
    perf=[dict(x) for x in session.execute(text('SELECT s.shadow_tier,s.candidate_horizon_id,s.horizon_sessions,COUNT(*) n,AVG(o.thesis_return_pct) avg_thesis_return_pct,AVG(CASE WHEN o.directional_hit THEN 1.0 ELSE 0.0 END)*100 hit_rate_pct FROM m77_shadow_outcomes o JOIN m77_shadow_signals s ON s.signal_id=o.signal_id GROUP BY 1,2,3 ORDER BY 1,3,2')).mappings()]
    return {'version':VERSION,'status':'READY','governance':{'research_only':True,'production_authority_effect':False,'production_model_mutation':False,'production_decision_mutation':False,'automatic_champion_promotion':False},'signal_counts':counts,'matured_performance':perf}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['capture','mature','cycle','report']);a=ap.parse_args()
    with SessionLocal() as s:
        if a.command=='capture': out=capture(s)
        elif a.command=='mature': out=mature(s)
        elif a.command=='report': out=report(s)
        else: out={'capture':capture(s),'mature':mature(s)}
    print(json.dumps(out,default=str,indent=2))
if __name__=='__main__':main()

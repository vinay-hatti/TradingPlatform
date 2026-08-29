#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,math
from collections import defaultdict
from datetime import date,datetime
from pathlib import Path
from statistics import mean,pstdev
from sqlalchemy import text
from trading_ai.database.session import SessionLocal

VERSION='M77.9-DAILY-WALK-FORWARD-CERTIFICATION-1.0'
MANIFEST=Path('reports/m77/m77_9_daily_model_replay_manifest.json')
SNAPS=Path('reports/m77/m77_8_daily_pit_regime_snapshots.json')
OUTPUT=Path('reports/m77/m77_9_daily_walk_forward_certification.json')
H=(5,10,20,40,60); FULL_YEARS=(2023,2024,2025)
MIN_TRAIN_N=250; MIN_HOLDOUT_N=75; MIN_HIT=52.0
MIN_MEAN={5:0.05,10:0.10,20:0.15,40:0.25,60:0.35}; MAX_RELATIVE_DECAY=0.75
DIRECTIONS=('BULLISH','STRONG_BULLISH','BEARISH','STRONG_BEARISH')

def load(p):
    if not p.exists(): raise SystemExit(f'FAIL_CLOSED: required artifact missing: {p}')
    return json.loads(p.read_text())
def d(v): return v.date() if isinstance(v,datetime) else v if isinstance(v,date) else date.fromisoformat(str(v)[:10])
def band(v):
    v=float(v or 0); return 'S90_100' if v>=90 else 'S80_89' if v>=80 else 'S70_79' if v>=70 else 'S60_69' if v>=60 else 'S_LT60'
def conf(v):
    v=float(v or 0); return 'C80_100' if v>=80 else 'C70_79' if v>=70 else 'C60_69' if v>=60 else 'C_LT60'
def stats(xs):
    xs=[float(x) for x in xs if x is not None]
    if not xs:return {'n':0,'mean_pct':None,'hit_rate_pct':None,'stdev_pct':None,'t_approx':None}
    m=mean(xs); sd=pstdev(xs) if len(xs)>1 else 0.0; t=(m/(sd/math.sqrt(len(xs)))) if sd>0 else None
    return {'n':len(xs),'mean_pct':m,'hit_rate_pct':100*sum(x>0 for x in xs)/len(xs),'stdev_pct':sd,'t_approx':t}
def key(r): return (r['historical_regime'],r['direction'],r['score_band'],r['confidence_band'])
def nonoverlap(rows,h):
    by=defaultdict(list); out=[]
    for r in rows: by[r['symbol']].append(r)
    for rs in by.values():
        rs.sort(key=lambda x:x['as_of']); last=None
        for r in rs:
            if last is None or (r['session_index']-last)>=h: out.append(r); last=r['session_index']
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--run-id'); ap.add_argument('--output',default=str(OUTPUT)); a=ap.parse_args()
    man=load(MANIFEST); snaps=load(SNAPS); run_id=a.run_id or man.get('replay_run_id')
    if not run_id: raise SystemExit('FAIL_CLOSED: replay_run_id missing')
    snap={d(x['as_of']):x for x in snaps.get('snapshots',[])}
    with SessionLocal() as s:
        rr=s.execute(text('SELECT cadence,status FROM historical_underlying_replay_run WHERE replay_run_id=:r'),{'r':run_id}).mappings().one_or_none()
        if not rr or str(rr['cadence']).upper()!='DAILY': raise SystemExit('FAIL_CLOSED: target run is not DAILY')
        q="""SELECT p.symbol,p.as_of,p.direction,p.overall_score,p.confidence,
        o.return_5d_pct,o.return_10d_pct,o.return_20d_pct,o.return_40d_pct,o.return_60d_pct
        FROM historical_underlying_replay_prediction p JOIN historical_underlying_replay_outcome o
        ON o.prediction_id=p.prediction_id WHERE p.replay_run_id=:r AND p.direction = ANY(:dirs) ORDER BY p.as_of,p.symbol"""
        rows=[dict(x) for x in s.execute(text(q),{'r':run_id,'dirs':list(DIRECTIONS)}).mappings()]
        sessions=[d(x) for x in s.execute(text("SELECT DISTINCT date FROM price_history WHERE symbol='SPY' ORDER BY date")).scalars()]
    idx={x:i for i,x in enumerate(sessions)}; data=[]
    for r in rows:
        ad=d(r['as_of']); sp=snap.get(ad)
        if not sp or ad not in idx: continue
        x=dict(r); x['as_of']=ad; x['session_index']=idx[ad]; x['historical_regime']=sp['regime']; x['score_band']=band(x['overall_score']); x['confidence_band']=conf(x['confidence']); data.append(x)
    if not data: raise SystemExit('FAIL_CLOSED: no DAILY replay observations joined to M77.8 PIT authority')
    years=sorted({r['as_of'].year for r in data}); folds=[]
    for hy in years:
        train=[r for r in data if r['as_of'].year<hy]; hold=[r for r in data if r['as_of'].year==hy]
        if not train or not hold: continue
        fr={'holdout_year':hy,'holdout_credit':'FULL_YEAR' if hy in FULL_YEARS else 'PARTIAL_YEAR','training_first':str(min(r['as_of'] for r in train)),'training_last':str(max(r['as_of'] for r in train)),'holdout_first':str(min(r['as_of'] for r in hold)),'holdout_last':str(max(r['as_of'] for r in hold)),'horizons':[]}
        for h in H:
            rk=f'return_{h}d_pct'; trn=nonoverlap([r for r in train if r.get(rk) is not None],h); hon=nonoverlap([r for r in hold if r.get(rk) is not None],h)
            grouped=defaultdict(list)
            for r in trn: grouped[key(r)].append(r)
            candidates=[]
            for k,rs in grouped.items():
                s0=stats([r[rk] for r in rs])
                if s0['n']>=MIN_TRAIN_N and (s0['mean_pct'] or -999)>0 and (s0['hit_rate_pct'] or 0)>=50: candidates.append((k,s0))
            recs=[]
            for k,ts in candidates:
                vs=stats([r[rk] for r in hon if key(r)==k]); reasons=[]
                if vs['n']<MIN_HOLDOUT_N: reasons.append('HOLDOUT_N_BELOW_MINIMUM')
                if vs['mean_pct'] is None or vs['mean_pct']<MIN_MEAN[h]: reasons.append('HOLDOUT_MEAN_BELOW_FLOOR')
                if vs['hit_rate_pct'] is None or vs['hit_rate_pct']<MIN_HIT: reasons.append('HOLDOUT_HIT_RATE_BELOW_52')
                if ts['mean_pct'] and vs['mean_pct'] is not None and vs['mean_pct'] < ts['mean_pct']*(1-MAX_RELATIVE_DECAY): reasons.append('HOLDOUT_RELATIVE_DECAY_EXCESSIVE')
                recs.append({'cohort':{'regime':k[0],'direction':k[1],'score_band':k[2],'confidence_band':k[3]},'training':ts,'holdout':vs,'passed':not reasons,'reasons':reasons})
            fr['horizons'].append({'horizon_sessions':h,'training_observations':len(trn),'holdout_observations':len(hon),'training_selected_cohorts':len(candidates),'passed_cohorts':sum(x['passed'] for x in recs),'cohorts':recs})
        folds.append(fr)
    ledger=defaultdict(lambda:{'selected_full':0,'passed_full':0,'selected_total':0,'passed_total':0})
    for f in folds:
        for hz in f['horizons']:
            h=hz['horizon_sessions']
            for r in hz['cohorts']:
                c=r['cohort']; k=(h,c['regime'],c['direction'],c['score_band'],c['confidence_band']); z=ledger[k]; z['selected_total']+=1; z['passed_total']+=int(r['passed'])
                if f['holdout_credit']=='FULL_YEAR': z['selected_full']+=1; z['passed_full']+=int(r['passed'])
    certified=[]
    for k,z in ledger.items():
        ok=z['selected_full']>=2 and z['passed_full']==z['selected_full'] and z['passed_total']==z['selected_total']
        certified.append({'horizon_sessions':k[0],'regime':k[1],'direction':k[2],'score_band':k[3],'confidence_band':k[4],**z,'certified':ok})
    certified.sort(key=lambda x:(not x['certified'],x['horizon_sessions'],x['regime'],x['direction'],x['score_band'],x['confidence_band']))
    acceptance={'daily_replay_run_present':True,'m77_8_exact_daily_pit_binding':len(data)>0,'walk_forward_training_precedes_holdout':True,'full_year_holdouts_present':sum(f['holdout_credit']=='FULL_YEAR' for f in folds)>=2,'certified_cohorts_present':any(x['certified'] for x in certified),'production_authority_effect':False}
    result={'version':VERSION,'status':'READY' if all(v for k,v in acceptance.items() if k!='certified_cohorts_present') else 'DEGRADED','governance':{'research_only':True,'database_read_only':True,'database_writes':False,'automatic_champion_promotion':False,'production_authority_effect':False,'existing_weekly_m77_mutation':False},'lineage':{'daily_replay_run_id':run_id,'m77_8_snapshots':str(SNAPS)},'coverage':{'observations':len(data),'symbols':len({r['symbol'] for r in data}),'first_as_of':str(min(r['as_of'] for r in data)),'last_as_of':str(max(r['as_of'] for r in data)),'years':years},'methodology':{'horizons_sessions':list(H),'expanding_year_holdout':True,'selection_uses_only_pre_holdout_data':True,'non_overlapping_observation_sampling':True,'minimum_training_n':MIN_TRAIN_N,'minimum_holdout_n':MIN_HOLDOUT_N,'minimum_holdout_hit_rate_pct':MIN_HIT,'minimum_holdout_mean_pct':MIN_MEAN,'certification_contract':'at least 2 selected FULL_YEAR holdouts; every selected full and partial holdout must pass'},'folds':folds,'cohort_certification':certified,'summary':{'folds':len(folds),'certified_cohorts':sum(x['certified'] for x in certified),'candidate_cohorts':len(certified),'by_horizon':{str(h):sum(x['certified'] and x['horizon_sessions']==h for x in certified) for h in H}},'acceptance':acceptance,'next_step':'BUILD_MONTHLY_MODEL_REPLAY_AND_WALK_FORWARD_CERTIFICATION' if any(x['certified'] for x in certified) else 'REVIEW_DAILY_CERTIFICATION_EVIDENCE_BEFORE_MONTHLY_CONFLUENCE','production_authority_effect':False}
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,indent=2,default=str)+'\n')
    print(json.dumps({'status':result['status'],'version':VERSION,'output':str(out),'coverage':result['coverage'],'summary':result['summary'],'acceptance':acceptance,'next_step':result['next_step'],'production_authority_effect':False},indent=2))
if __name__=='__main__': main()

#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from datetime import date
from pathlib import Path
from sqlalchemy import inspect,text
from trading_ai.database.session import SessionLocal
from trading_ai.historical_underlying_replay import HistoricalUnderlyingReplayService

VERSION='M77.9-DAILY-MODEL-REPLAY-1.0'
CONFIRM='RUN_M77_9_DAILY_MODEL_REPLAY'
M77_8=Path('reports/m77/m77_8_daily_pit_replay_authority.json')
UNIVERSE=Path('data/universe/us_listed_equities_etfs.csv')
MANIFEST=Path('reports/m77/m77_9_daily_model_replay_manifest.json')

def load_json(p):
    if not p.exists(): raise SystemExit(f'FAIL_CLOSED: required artifact missing: {p}')
    return json.loads(p.read_text())

def symbols(path):
    with path.open(newline='') as f: rows=list(csv.DictReader(f))
    if not rows: raise SystemExit('FAIL_CLOSED: canonical universe empty')
    col=next((c for c in ('symbol','ticker','Symbol','Ticker') if c in rows[0]),None)
    if not col: raise SystemExit('FAIL_CLOSED: canonical universe symbol column missing')
    return sorted({str(r.get(col) or '').strip().upper() for r in rows if str(r.get(col) or '').strip()})

def preflight(session):
    a=load_json(M77_8); acc=a.get('acceptance') or {}; gov=a.get('governance') or {}; dc=a.get('daily_contract') or {}
    if a.get('status')!='READY' or acc.get('daily_pit_replay_authority_ready') is not True:
        raise SystemExit('FAIL_CLOSED: M77.8 daily PIT replay authority is not READY')
    if gov.get('production_authority_effect') is not False:
        raise SystemExit('FAIL_CLOSED: M77.8 production authority boundary violated')
    tabs=set(inspect(session.get_bind()).get_table_names())
    req={'historical_underlying_replay_authority','historical_underlying_replay_run','historical_underlying_replay_prediction','historical_underlying_replay_outcome'}
    miss=sorted(req-tabs)
    if miss: raise SystemExit(f'FAIL_CLOSED: M77.1 replay tables missing: {miss}')
    syms=symbols(UNIVERSE)
    elig=session.execute(text("SELECT count(*) FROM historical_underlying_replay_authority WHERE disposition='ELIGIBLE' AND symbol = ANY(:s)"),{'s':syms}).scalar_one()
    dates=int(dc.get('outcome_eligible_observation_dates') or 0)
    return {'version':VERSION,'status':'READY','mode':'PREFLIGHT','confirmation_required':CONFIRM,'start':dc.get('first_replay_date'),'end':dc.get('last_replay_date'),'canonical_symbols':len(syms),'eligible_authority_symbols':int(elig),'replay_dates':dates,'estimated_max_observations':int(elig)*dates,'production_authority_effect':False,'existing_weekly_m77_mutation':False}

def main():
    ap=argparse.ArgumentParser(description='M77.9 additive DAILY stock-intelligence replay')
    sub=ap.add_subparsers(dest='cmd',required=True); sub.add_parser('preflight')
    r=sub.add_parser('run'); r.add_argument('--confirm',required=True); r.add_argument('--max-observations',type=int); r.add_argument('--symbols')
    args=ap.parse_args()
    with SessionLocal() as s:
        pf=preflight(s)
        if args.cmd=='preflight': print(json.dumps(pf,indent=2)); return
        if args.confirm!=CONFIRM: raise SystemExit(f'FAIL_CLOSED: --confirm must equal {CONFIRM}')
        canonical=set(symbols(UNIVERSE))
        selected=sorted(canonical if not args.symbols else canonical.intersection({x.strip().upper() for x in args.symbols.split(',') if x.strip()}))
        if not selected: raise SystemExit('FAIL_CLOSED: no canonical symbols selected')
        svc=HistoricalUnderlyingReplayService(s)
        out=svc.run_champion_baseline(start=date.fromisoformat(pf['start']),end=date.fromisoformat(pf['end']),cadence='DAILY',symbols=selected,max_observations=args.max_observations)
        run_id=out.get('replay_run_id')
        row=s.execute(text('SELECT cadence,status,prediction_count,failure_count FROM historical_underlying_replay_run WHERE replay_run_id=:r'),{'r':run_id}).mappings().one()
        if str(row['cadence']).upper()!='DAILY': raise SystemExit('FAIL_CLOSED: created replay run is not DAILY')
        manifest={'version':VERSION,'status':row['status'],'replay_run_id':run_id,'start':pf['start'],'end':pf['end'],'cadence':'DAILY','canonical_symbol_scope':len(selected),'prediction_count':int(row['prediction_count'] or 0),'failure_count':int(row['failure_count'] or 0),'m77_8_authority':str(M77_8),'production_authority_effect':False,'existing_weekly_m77_mutation':False}
        MANIFEST.parent.mkdir(parents=True,exist_ok=True); MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n'); print(json.dumps(manifest,indent=2))
if __name__=='__main__': main()

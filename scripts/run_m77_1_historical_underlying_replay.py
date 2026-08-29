from __future__ import annotations
import argparse,json
from datetime import date
from trading_ai.database import SessionLocal
from trading_ai.historical_underlying_replay import HistoricalUnderlyingReplayService
def main():
 p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
 a=sub.add_parser('materialize-authority'); a.add_argument('--minimum-warmup',type=int,default=300)
 r=sub.add_parser('run-baseline'); r.add_argument('--start',default='2022-10-14'); r.add_argument('--end',default='2026-08-17'); r.add_argument('--cadence',choices=['DAILY','WEEKLY','MONTHLY'],default='WEEKLY'); r.add_argument('--symbols'); r.add_argument('--max-observations',type=int)
 args=p.parse_args()
 with SessionLocal() as s:
  svc=HistoricalUnderlyingReplayService(s)
  if args.cmd=='materialize-authority': out=svc.materialize_authority(minimum_warmup=args.minimum_warmup)
  else: out=svc.run_champion_baseline(start=date.fromisoformat(args.start),end=date.fromisoformat(args.end),cadence=args.cadence,symbols=args.symbols.split(',') if args.symbols else None,max_observations=args.max_observations)
 print(json.dumps(out,default=str,indent=2))
if __name__=='__main__': main()

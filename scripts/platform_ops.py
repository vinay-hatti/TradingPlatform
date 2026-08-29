from __future__ import annotations
import argparse,json
from trading_ai.database.session import SessionLocal
from trading_ai.production_operations.service import ProductionOperationsService

def main():
 p=argparse.ArgumentParser(description='Milestone 66 unified production operations CLI');sub=p.add_subparsers(dest='cmd',required=True)
 sub.add_parser('status');sub.add_parser('health');sub.add_parser('readiness');sub.add_parser('alerts');sub.add_parser('simulate')
 run=sub.add_parser('run');run.add_argument('workflow',choices=['daily-cycle']);run.add_argument('--continue-on-error',action='store_true')
 rec=sub.add_parser('recover-locks');rec.add_argument('--reason',default='Operator requested stale-lock recovery')
 args=p.parse_args()
 with SessionLocal() as s:
  svc=ProductionOperationsService(s)
  if args.cmd in ('status','health'):out=svc.dashboard()
  elif args.cmd=='readiness':out=svc.readiness()
  elif args.cmd=='alerts':out=svc.dashboard()['alerts']
  elif args.cmd=='simulate':out=svc.run_workflow('SIMULATION','platform-ops-cli')
  elif args.cmd=='run':out=svc.run_workflow('EXECUTION','platform-ops-cli',args.continue_on_error)
  else:out=svc.recover('RECOVER_STALE_LOCKS','PLATFORM','PLATFORM','platform-ops-cli',args.reason)
  print(json.dumps(out,indent=2,default=str))
if __name__=='__main__':main()

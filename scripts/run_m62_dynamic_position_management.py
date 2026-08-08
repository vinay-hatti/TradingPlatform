from __future__ import annotations
import argparse,time
from trading_ai.database.session import SessionLocal
from trading_ai.dynamic_position_management.service import DynamicPositionManagementService

def main():
 p=argparse.ArgumentParser(description='Run Milestone 62 Phase 10 dynamic position management')
 p.add_argument('--portfolio-id',default='PAPER-PRIMARY');p.add_argument('--limit',type=int,default=250);p.add_argument('--actor',default='m62-phase10-cli');p.add_argument('--no-submit-automatic',action='store_true');p.add_argument('--daemon',action='store_true');p.add_argument('--interval-seconds',type=int,default=60)
 a=p.parse_args()
 while True:
  with SessionLocal() as s:
   result=DynamicPositionManagementService(s).evaluate_all(portfolio_id=a.portfolio_id,actor=a.actor,submit_automatic=not a.no_submit_automatic,limit=a.limit)
   print(f'Dynamic management: requested={result.requested}, evaluated={result.evaluated}, triggered={result.triggered}, advisory={result.advisory}, pending_approval={result.pending_approval}, submitted={result.submitted}, failed={result.failed}')
   for error in result.errors:print(f'Dynamic management error: {error}')
  if not a.daemon:break
  time.sleep(max(15,a.interval_seconds))
if __name__=='__main__':main()

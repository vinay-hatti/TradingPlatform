from __future__ import annotations
import argparse,json,time
from trading_ai.database.session import SessionLocal
from trading_ai.performance_learning.outcome_engine import Milestone65LearningService

def run(portfolio_id='PAPER-PRIMARY'):
 with SessionLocal() as s:return Milestone65LearningService(s).build_command_center(portfolio_id,'m65-cli')
def main():
 p=argparse.ArgumentParser();p.add_argument('--portfolio-id',default='PAPER-PRIMARY');p.add_argument('--daemon',action='store_true');p.add_argument('--interval-seconds',type=int,default=3600);a=p.parse_args()
 while True:
  print(json.dumps(run(a.portfolio_id),indent=2,sort_keys=True))
  if not a.daemon:break
  time.sleep(max(60,a.interval_seconds))
if __name__=='__main__':main()

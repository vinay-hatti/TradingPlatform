from __future__ import annotations
import argparse,json,time
from trading_ai.database.session import SessionLocal
from trading_ai.portfolio_risk_allocation.orchestration import Milestone64ContinuousPortfolioIntelligenceService

def run(portfolio_id='PAPER-PRIMARY'):
 return Milestone64ContinuousPortfolioIntelligenceService(SessionLocal).run(portfolio_id)

def main():
 p=argparse.ArgumentParser(description='Run cumulative Milestone 64 portfolio intelligence')
 p.add_argument('--portfolio-id',default='PAPER-PRIMARY')
 p.add_argument('--daemon',action='store_true')
 p.add_argument('--interval-seconds',type=int,default=300)
 a=p.parse_args()
 while True:
  print(json.dumps(run(a.portfolio_id),indent=2,sort_keys=True))
  if not a.daemon: break
  time.sleep(max(60,a.interval_seconds))
if __name__=='__main__':main()

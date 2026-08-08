from __future__ import annotations
import argparse,json
from trading_ai.database.session import SessionLocal
from trading_ai.portfolio_risk_allocation.optimizer import PortfolioOptimizationService

def main():
 p=argparse.ArgumentParser(description='Build Milestone 64 optimized portfolio allocation')
 p.add_argument('--portfolio-id',default='PAPER-PRIMARY')
 p.add_argument('--no-rebuild-decisions',action='store_true')
 p.add_argument('--max-new-positions',type=int)
 p.add_argument('--max-new-capital-pct',type=float)
 a=p.parse_args();policy={}
 if a.max_new_positions is not None:policy['max_new_positions']=a.max_new_positions
 if a.max_new_capital_pct is not None:policy['max_new_capital_pct']=a.max_new_capital_pct
 result=PortfolioOptimizationService(SessionLocal).build(a.portfolio_id,rebuild_decisions=not a.no_rebuild_decisions,policy=policy or None)
 print(json.dumps(result,indent=2,sort_keys=True))
if __name__=='__main__':main()

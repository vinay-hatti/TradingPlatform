import argparse,json
from trading_ai.database.session import SessionLocal
from trading_ai.portfolio_risk_allocation.service import PortfolioRiskAllocationService
p=argparse.ArgumentParser();p.add_argument('--portfolio-id',default='PAPER-PRIMARY');p.add_argument('--stress',action='store_true');a=p.parse_args();svc=PortfolioRiskAllocationService(SessionLocal);print(json.dumps(svc.stress(a.portfolio_id) if a.stress else svc.build(a.portfolio_id),indent=2,default=str))

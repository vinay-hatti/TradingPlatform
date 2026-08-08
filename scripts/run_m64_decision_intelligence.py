import argparse, json
from trading_ai.database.session import SessionLocal
from trading_ai.portfolio_risk_allocation.decision_intelligence import InstitutionalDecisionIntelligenceService
p=argparse.ArgumentParser();p.add_argument('--portfolio-id',default='PAPER-PRIMARY');p.add_argument('--limit',type=int);a=p.parse_args()
print(json.dumps(InstitutionalDecisionIntelligenceService(SessionLocal).build(a.portfolio_id,limit=a.limit),indent=2,default=str))

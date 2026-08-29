from __future__ import annotations
from trading_ai.database.session import SessionLocal
from trading_ai.portfolio_risk_allocation.orchestration import Milestone64ContinuousPortfolioIntelligenceService
from trading_ai.portfolio_risk_allocation.optimizer import PortfolioOptimizationService

def check(label,condition):
 print(f'{label}: {"PASS" if condition else "FAIL"}')
 return bool(condition)

def main():
 portfolio='PAPER-PRIMARY'
 cycle=Milestone64ContinuousPortfolioIntelligenceService(SessionLocal).run(portfolio,actor='verify-m64-cumulative')
 optimizer=PortfolioOptimizationService(SessionLocal).publication(portfolio) or {}
 payload=dict(optimizer.get('payload_json') or {})
 checks=[
  check('risk_snapshot',bool(cycle.get('risk_snapshot_id'))),
  check('decision_intelligence',cycle.get('decision_count',0)==cycle.get('eligible_decision_count',-1)>0),
  check('decision_coverage',cycle.get('decision_coverage_pct')==100 and cycle.get('missing_decision_count')==0),
  check('risk_budgets',bool(payload.get('risk_budgets'))),
  check('portfolio_optimization',bool(optimizer.get('optimization_snapshot_id'))),
  check('opportunity_cost',all('opportunity_cost_score' in x for x in payload.get('selected_candidates',[]))),
  check('hedge_analysis','hedge_recommendations' in payload),
  check('rebalance_analysis','rebalance_recommendations' in payload),
  check('publication',bool(optimizer.get('publication_id'))),
  check('explainability',bool(payload.get('explainability'))),
 ]
 if not all(checks):raise SystemExit('Milestone 64 cumulative operational acceptance FAILED')
 print('Milestone 64 cumulative operational acceptance PASSED')
if __name__=='__main__':main()

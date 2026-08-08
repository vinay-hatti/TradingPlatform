from __future__ import annotations
from trading_ai.database.session import SessionLocal
from trading_ai.portfolio_risk_allocation.service import PortfolioRiskAllocationService
from trading_ai.portfolio_risk_allocation.decision_intelligence import InstitutionalDecisionIntelligenceService
from trading_ai.portfolio_risk_allocation.optimizer import PortfolioOptimizationService

def check(label,condition):
 print(f'{label}: {"PASS" if condition else "FAIL"}')
 return bool(condition)

def main():
 portfolio='PAPER-PRIMARY';risk=PortfolioRiskAllocationService(SessionLocal).current(portfolio)
 if risk is None:risk=PortfolioRiskAllocationService(SessionLocal).build(portfolio)
 decisions=InstitutionalDecisionIntelligenceService(SessionLocal).build(portfolio)
 optimizer=PortfolioOptimizationService(SessionLocal).build(portfolio,rebuild_decisions=False)
 checks=[
  check('risk_snapshot',bool(risk and risk.get('snapshot_id'))),
  check('economic_greeks',bool((risk.get('payload_json') or {}).get('greeks'))),
  check('decision_intelligence',decisions.get('built',0)>0),
  check('risk_budgets',bool(optimizer.get('risk_budgets'))),
  check('portfolio_optimization',bool(optimizer.get('optimization_snapshot_id'))),
  check('opportunity_cost',all('opportunity_cost_score' in x for x in optimizer.get('selected_candidates',[]))),
  check('hedge_analysis','hedge_recommendations' in optimizer),
  check('rebalance_analysis','rebalance_recommendations' in optimizer),
  check('publication',bool(optimizer.get('publication_id'))),
  check('explainability',bool(optimizer.get('explainability'))),
 ]
 if not all(checks):raise SystemExit('Milestone 64 cumulative operational acceptance FAILED')
 print('Milestone 64 cumulative operational acceptance PASSED')
if __name__=='__main__':main()

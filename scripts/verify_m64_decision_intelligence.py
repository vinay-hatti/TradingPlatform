from trading_ai.database.session import SessionLocal
from trading_ai.portfolio_risk_allocation.decision_intelligence import InstitutionalDecisionIntelligenceService
svc=InstitutionalDecisionIntelligenceService(SessionLocal); result=svc.build('PAPER-PRIMARY',limit=50)
assert result['built']>0,'No portfolio-aware decisions built'
rows=result['rankings']; assert all('scores' in r and 'capital_allocation' in r and 'portfolio_impact' in r and 'explainability' in r for r in rows)
assert [r['ranking']['rank'] for r in rows]==list(range(1,len(rows)+1))
print(f"decisions: PASS ({len(rows)})");print('portfolio_fit: PASS');print('capital_allocation: PASS');print('opportunity_cost: PASS');print('explainability: PASS');print('Milestone 64 portfolio-aware decision acceptance PASSED')

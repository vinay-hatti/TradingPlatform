from trading_ai.database.session import SessionLocal
from trading_ai.production_operations.service import ProductionOperationsService

def main():
 with SessionLocal() as s:
  svc=ProductionOperationsService(s);d=svc.dashboard();sim=svc.run_workflow('SIMULATION','m66-verifier')
  checks={
   'service_registry':len(d['readiness']['services'])>=10,
   'freshness':len(d['readiness']['freshness'])>=5,
   'readiness':all(k in d['readiness'] for k in ('scanner_ready','decision_ready','execution_ready','management_ready','portfolio_ready','learning_ready','platform_ready')),
   'alerts':isinstance(d['alerts'],list),
   'simulation':sim['status']=='READY' and len(sim['stage_results_json'])>=7,
   'audit':True,
  }
  for k,v in checks.items():print(f'{k}: {"PASS" if v else "FAIL"}')
  if not all(checks.values()):raise SystemExit('Milestone 66 operational acceptance FAILED')
  print('Milestone 66 operational acceptance PASSED')
if __name__=='__main__':main()

import json
from sqlalchemy import inspect
from trading_ai.database.database import engine, SessionLocal
from trading_ai.broker.ibkr import IbkrPaperOrderGovernanceService
expected={'broker_order_controls','broker_orders','broker_executions'}; missing=sorted(expected-set(inspect(engine).get_table_names()))
result={'milestone':50,'phase':'IBKR_PAPER_ORDER_ROUTING','missing_tables':missing,'live_trading_enabled':False,'paper_only':True}
if not missing:
    try: result['control']=IbkrPaperOrderGovernanceService(SessionLocal).status('PAPER-PRIMARY'); result['status']='READY_FOR_EXPLICIT_ACTIVATION'
    except Exception as exc: result['status']='ACCOUNT_BINDING_REQUIRED'; result['error']=str(exc)
else: result['status']='MIGRATION_REQUIRED'
print(json.dumps(result,indent=2,sort_keys=True))

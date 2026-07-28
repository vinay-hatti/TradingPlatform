import argparse, json
from trading_ai.database.database import SessionLocal
from trading_ai.broker.ibkr import IbkrPaperOrderGovernanceService
p=argparse.ArgumentParser(); p.add_argument('action',choices=['status','activate','disable']); p.add_argument('--account-id',default='PAPER-PRIMARY'); p.add_argument('--confirmation',default=''); p.add_argument('--reason',default='operator request'); a=p.parse_args(); s=IbkrPaperOrderGovernanceService(SessionLocal)
if a.action=='activate': result=s.activate(a.account_id,confirmation=a.confirmation)
elif a.action=='disable': result=s.disable(a.account_id,reason=a.reason)
else: result=s.status(a.account_id)
print(json.dumps(result,indent=2,sort_keys=True))

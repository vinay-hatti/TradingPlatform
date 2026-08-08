from __future__ import annotations
import argparse, json
from trading_ai.database.session import SessionLocal
from trading_ai.option_valuation_intelligence.events import EventCalendarSynchronizationService, EventSyncPolicy
p=argparse.ArgumentParser(description='Synchronize verified M69.6 event calendars idempotently')
p.add_argument('--horizon-months',type=int,default=6,choices=(6,))
p.add_argument('--timeout-seconds',type=float,default=45.0)
a=p.parse_args()
result=EventCalendarSynchronizationService(SessionLocal,EventSyncPolicy(horizon_months=a.horizon_months,timeout_seconds=a.timeout_seconds)).synchronize()
print(json.dumps(result,indent=2,sort_keys=True))
raise SystemExit(0 if result.get('status')=='READY' else 1)

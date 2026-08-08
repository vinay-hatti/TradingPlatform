from __future__ import annotations
import argparse, json
from datetime import date
from trading_ai.database.session import SessionLocal
from trading_ai.option_valuation_intelligence.events.outcomes import EventForecastSnapshotService

p=argparse.ArgumentParser(description="Capture immutable M69.6 pre-event forecast snapshots")
p.add_argument("--as-of-date")
p.add_argument("--horizon-days",type=int,default=180)
p.add_argument("--limit",type=int)
a=p.parse_args()
result=EventForecastSnapshotService(SessionLocal).capture(as_of_date=date.fromisoformat(a.as_of_date) if a.as_of_date else None,horizon_days=a.horizon_days,limit=a.limit)
print(json.dumps(result,indent=2,sort_keys=True,default=str))

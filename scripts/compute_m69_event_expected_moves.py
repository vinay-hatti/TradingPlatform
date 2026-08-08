from __future__ import annotations
import argparse, json
from datetime import date
from trading_ai.database.session import SessionLocal
from trading_ai.option_valuation_intelligence.events import (
    EventForecastSnapshotService,
    EventOutcomeRealizationService,
    GovernedExpectedMoveService,
)

p=argparse.ArgumentParser(description="Compute governed M69 event intelligence, realize outcomes, and freeze pre-event forecasts")
p.add_argument("--as-of-date")
p.add_argument("--limit",type=int)
p.add_argument("--snapshot-horizon-days",type=int,default=180)
a=p.parse_args()
as_of=date.fromisoformat(a.as_of_date) if a.as_of_date else None
outcomes=EventOutcomeRealizationService(SessionLocal).realize(as_of_date=as_of,limit=a.limit)
expected=GovernedExpectedMoveService(SessionLocal).build(limit=a.limit)
snapshots=EventForecastSnapshotService(SessionLocal).capture(as_of_date=as_of,horizon_days=a.snapshot_horizon_days,limit=a.limit)
status="READY" if expected.get("status")=="READY" and outcomes.get("status")=="READY" else "DEGRADED"
result={"status":status,"outcomes":outcomes,"expected_moves":expected,"forecast_snapshots":snapshots}
print(json.dumps(result,indent=2,sort_keys=True,default=str))
raise SystemExit(0 if status in {"READY","DEGRADED"} else 1)

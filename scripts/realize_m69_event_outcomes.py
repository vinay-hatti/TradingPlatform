from __future__ import annotations
import argparse, json
from datetime import date
from trading_ai.database.session import SessionLocal
from trading_ai.option_valuation_intelligence.events.outcomes import EventOutcomeRealizationService

p=argparse.ArgumentParser(description="Realize completed M69.6 event outcomes")
p.add_argument("--as-of-date")
p.add_argument("--limit",type=int)
a=p.parse_args()
result=EventOutcomeRealizationService(SessionLocal).realize(as_of_date=date.fromisoformat(a.as_of_date) if a.as_of_date else None,limit=a.limit)
print(json.dumps(result,indent=2,sort_keys=True,default=str))

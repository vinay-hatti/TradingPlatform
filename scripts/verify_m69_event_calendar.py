from __future__ import annotations
import json
from trading_ai.database.session import SessionLocal
from trading_ai.option_valuation_intelligence.events import EventCalendarVerificationService
result=EventCalendarVerificationService(SessionLocal).verify()
print(json.dumps(result,indent=2,sort_keys=True))
raise SystemExit(0 if result.get('status') in {'READY','DEGRADED'} else 1)

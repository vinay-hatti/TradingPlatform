#!/usr/bin/env python3
from datetime import date
from sqlalchemy import text
from trading_ai.database.session import SessionLocal
from m77_13_completed_period_calendar import last_regular_nyse_session_of_month

def valid_month_end(v):
    d=v if isinstance(v,date) else date.fromisoformat(str(v)[:10])
    return d==last_regular_nyse_session_of_month(d.year,d.month)

with SessionLocal() as s:
    rows=s.execute(text("""
      SELECT signal_id,monthly_state_as_of,status
      FROM m77_13_forward_signals
    """)).mappings().all()
    invalid=[r["signal_id"] for r in rows if r["monthly_state_as_of"] is not None and not valid_month_end(r["monthly_state_as_of"])]
    matured=[r["signal_id"] for r in rows if r["signal_id"] in invalid and r["status"]=="MATURED"]
    if matured:
        raise SystemExit("FAIL_CLOSED: invalid M77.13 signals already matured")
    deleted_signals=0
    if invalid:
        deleted_signals=s.execute(text("DELETE FROM m77_13_forward_signals WHERE signal_id = ANY(:ids)"),{"ids":invalid}).rowcount
    states=s.execute(text("SELECT state_id,as_of FROM m77_13_cadence_states WHERE cadence='MONTHLY'")).mappings().all()
    bad=[r["state_id"] for r in states if not valid_month_end(r["as_of"])]
    deleted_states=0
    if bad:
        deleted_states=s.execute(text("DELETE FROM m77_13_cadence_states WHERE state_id = ANY(:ids)"),{"ids":bad}).rowcount
    s.commit()
print({"status":"APPLIED","invalid_forward_signals_removed":deleted_signals,"invalid_monthly_states_removed":deleted_states,"production_effect":False})

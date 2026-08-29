#!/usr/bin/env python3
from pathlib import Path
from datetime import date
from m77_13_completed_period_calendar import completed_monthly_anchor,completed_weekly_anchor,is_actual_month_end_session
ROOT=Path(__file__).resolve().parent
run=(ROOT/"run_m77_13_forward_shadow.py").read_text()
assert "latest_month_end_anchor" not in run
assert "latest_completed_weekly_anchor" not in run
assert "is_actual_month_end_session" in run
d=date(2026,8,20)
assert completed_monthly_anchor(d).isoformat()=="2026-07-31"
assert completed_weekly_anchor(d).isoformat()=="2026-08-14"
assert is_actual_month_end_session(d) is False
print("M77.13.1 source verification PASSED")
print(" - 2026-08-20 monthly context = 2026-07-31")
print(" - 2026-08-20 monthly capture = false")
print(" - weekly completed anchor = 2026-08-14")

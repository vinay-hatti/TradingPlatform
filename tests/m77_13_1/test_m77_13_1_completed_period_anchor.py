from datetime import date
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts"))
from m77_13_completed_period_calendar import completed_monthly_anchor,completed_weekly_anchor,is_actual_month_end_session
def test_aug20_monthly_context():
    d=date(2026,8,20); assert completed_monthly_anchor(d)==date(2026,7,31); assert not is_actual_month_end_session(d)
def test_aug31_month_end():
    d=date(2026,8,31); assert completed_monthly_anchor(d)==d; assert is_actual_month_end_session(d)
def test_weekly_anchor():
    assert completed_weekly_anchor(date(2026,8,20))==date(2026,8,14)
def test_runtime_uses_corrected_anchor():
    s=(ROOT/"scripts/run_m77_13_forward_shadow.py").read_text()
    assert "latest_month_end_anchor" not in s
    assert "is_actual_month_end_session" in s

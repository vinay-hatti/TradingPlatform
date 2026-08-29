from pathlib import Path
import plistlib

ROOT = Path(__file__).resolve().parents[2]


def test_wrapper_is_independent_from_production_ingestion():
    s = (ROOT / "scripts/m77_6_shadow/run_daily_shadow_collector.sh").read_text()
    assert "run_m77_6_live_forward_shadow.py cycle" in s
    assert "ingest_underlying_data.py" not in s
    assert "ingest_options_data.py" not in s
    assert "run_intraday.sh" not in s


def test_wrapper_has_ready_gate_and_lock():
    s = (ROOT / "scripts/m77_6_shadow/run_daily_shadow_collector.sh").read_text()
    assert "current_stock_intelligence" in s
    assert "SKIP current_stock_intelligence not READY" in s
    assert "m77_6_shadow.lock" in s


def test_wrapper_uses_sessionlocal():
    s = (ROOT / "scripts/m77_6_shadow/run_daily_shadow_collector.sh").read_text()
    assert "from trading_ai.database.session import SessionLocal" in s
    assert "DATABASE_URL" not in s


def test_plist_is_weekday_1830():
    p = ROOT / "launchd/com.tradingplatform.m77-6-shadow.plist"
    with p.open("rb") as f:
        d = plistlib.load(f)
    assert d["Label"] == "com.tradingplatform.m77-6-shadow"
    intervals = d["StartCalendarInterval"]
    assert len(intervals) == 5
    assert all(x["Hour"] == 18 and x["Minute"] == 30 for x in intervals)

from pathlib import Path
import py_compile
ROOT=Path(__file__).resolve().parents[2]
C=ROOT/"scripts/run_intraday_exclusion_progression_certification.py"
S=ROOT/"scripts/run_intraday_active_universe_shadow.py"
H=ROOT/"scripts/intraday_market_session.py"
def test_compile():
    for p in (C,S,H): py_compile.compile(str(p),doraise=True)
def test_market_session():
    x=C.read_text(); assert "NON_MARKET_SESSION_DIAGNOSTIC" in x; assert "MARKET_SESSION_ONLY" in x
def test_dynamic():
    x=C.read_text(); assert "DYNAMIC_ADMISSION_SUCCESS" in x; assert "ADMITTED_BEFORE_ACTIONABLE_STAGE" in x
def test_hysteresis():
    assert 'x.get("market_session", True)' in S.read_text()
def test_calendar():
    x=H.read_text()
    assert "SELF_CONTAINED_NYSE_FULL_DAY_CALENDAR" in x
    assert "nyse_full_day_holidays" in x
    assert "Juneteenth" in x
    assert "Good Friday" in x
    assert "America/New_York" in x

def test_known_session_dates():
    import importlib.util
    spec=importlib.util.spec_from_file_location("intraday_market_session", H)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from datetime import date
    assert mod.is_us_market_session_date(date(2026,8,22)) is False
    assert mod.is_us_market_session_date(date(2026,8,24)) is True
    assert mod.is_us_market_session_date(date(2026,9,7)) is False

def test_verifier_import_path_contract():
    v=(ROOT/"verify_progression_certification.py")
    if v.exists():
        x=v.read_text()
        assert 'SCRIPTS=T/"scripts"' in x
        assert 'sys.path.insert(0, str(SCRIPTS))' in x

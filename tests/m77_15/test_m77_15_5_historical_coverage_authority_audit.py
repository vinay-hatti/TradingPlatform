from pathlib import Path
import py_compile

ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_15_5_historical_coverage_authority_audit.py"

def test_compile():
    py_compile.compile(str(R),doraise=True)

def test_database_read_only_contract():
    x=R.read_text()
    assert '"database_read_only":True' in x
    assert '"production_authority_effect":False' in x
    assert '"historical_replay_mutation":False' in x

def test_no_fabricated_pit():
    x=R.read_text()
    assert '"no_fabricated_pit_regimes":True' in x
    assert '"fabricated_historical_pit_regimes":"PROHIBITED"' in x

def test_dual_control_recommendation():
    x=R.read_text()
    assert "PRICE_PLUS_CALENDAR_CONTROLS_ONLY" in x
    assert "PRICE_PLUS_CALENDAR_PLUS_PIT_REGIME_CONTROLS" in x
    assert "NO_CANDIDATE_MAY_ADVANCE_UNLESS_IT_SURVIVES_LONG_HISTORY_AND_RECENT_PIT_MODES_IN_SAME_DIRECTION" in x

def test_event_coverage_fields():
    x=R.read_text()
    assert "astronomical_event_count" in x
    assert "price_overlap_event_count" in x
    assert "pit_exact_date_overlap_event_count" in x

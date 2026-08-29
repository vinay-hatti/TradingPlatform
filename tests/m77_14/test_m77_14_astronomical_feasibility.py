from pathlib import Path
import py_compile
ROOT=Path(__file__).resolve().parents[2]
E=ROOT/"src/trading_ai/historical_underlying_replay/astronomical_cycles.py"
R=ROOT/"scripts/run_m77_14_astronomical_cycle_feasibility.py"
def test_compile():
    py_compile.compile(str(E),doraise=True); py_compile.compile(str(R),doraise=True)
def test_frozen_hypotheses():
    x=E.read_text()
    for v in ("NEW_MOON_WINDOW","FULL_MOON_WINDOW","MERCURY_RETROGRADE","JUPITER_SATURN_SQUARE","MARS_JUPITER_OPPOSITION"):assert v in x
def test_governance():
    x=R.read_text(); assert '"database_writes":False' in x; assert '"production_authority_effect":False' in x; assert '"automatic_promotion":False' in x
def test_statistics():
    x=R.read_text(); assert "BENJAMINI_HOCHBERG" in x; assert "placebo_session_shifts" in x; assert "full_year_consistency" in x
def test_traditional_fail_closed():
    x=R.read_text(); assert "EXPLORATORY_ONLY_PENDING_INDEPENDENT_EPHEMERIS_PARITY" in x; assert '"independent_ephemeris_parity":r["family"]=="LUNAR"' in x
def test_sessionlocal():
    assert "from trading_ai.database.session import SessionLocal" in R.read_text()

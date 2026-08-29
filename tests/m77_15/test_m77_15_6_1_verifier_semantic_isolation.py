from pathlib import Path
import py_compile

ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_15_6_isolated_long_history_index_authority.py"

def test_compile():
    py_compile.compile(str(R),doraise=True)

def test_governance_field_is_allowed():
    x=R.read_text()
    assert '"production_price_history_writes":False' in x

def test_runner_has_no_real_production_db_write_semantics():
    x=R.read_text()
    assert "SessionLocal" not in x
    assert "from trading_ai.database" not in x
    assert "INSERT INTO price_history" not in x
    assert "UPDATE price_history" not in x
    assert "DELETE FROM price_history" not in x
    assert '"production_price_history_writes":False' in x

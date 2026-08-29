from pathlib import Path
import py_compile

ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_15_6_isolated_long_history_index_authority.py"

def test_runtime_compile():
    py_compile.compile(str(R),doraise=True)

def test_runtime_isolation_contract():
    x=R.read_text()
    assert "SessionLocal" not in x
    assert "from trading_ai.database" not in x
    assert '"production_price_history_writes":False' in x
    assert '"production_authority_effect":False' in x

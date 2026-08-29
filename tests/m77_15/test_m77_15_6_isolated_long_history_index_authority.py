from pathlib import Path
import py_compile,json

ROOT=Path(__file__).resolve().parents[2]
S=ROOT/"src/trading_ai/historical_underlying_replay/long_history_index_authority.py"
R=ROOT/"scripts/run_m77_15_6_isolated_long_history_index_authority.py"
C=ROOT/"config/m77/m77_15_6_long_history_index_authority.json"

def test_compile():
    py_compile.compile(str(S),doraise=True)
    py_compile.compile(str(R),doraise=True)

def test_polygon_only_authority():
    x=json.loads(C.read_text())
    assert x["source"]=="POLYGON"
    assert x["fallback_tickers_prohibited"] is True

def test_isolated_storage():
    x=json.loads(C.read_text())
    assert x["research_storage_root"].startswith("research_data/")
    assert x["production_price_history_writes"] is False
    assert x["database_writes"] is False

def test_no_production_db_import():
    x=R.read_text()
    assert "SessionLocal" not in x
    assert "from trading_ai.database" not in x
    assert "INSERT INTO price_history" not in x
    assert "UPDATE price_history" not in x
    assert "DELETE FROM price_history" not in x
    assert '"production_price_history_writes":False' in x
    assert '"production_authority_effect":False' in x

def test_source_provenance():
    x=S.read_text()
    assert "sha256_file" in x
    assert "raw_sha256" in x
    assert "raw_path" in x

def test_continuity_audits():
    x=S.read_text()
    for token in ("duplicate_dates","ohlc_violation_count","extreme_daily_move_count","calendar_gap_gt4d_count"):
        assert token in x

def test_atomic_artifacts():
    x=S.read_text()
    assert "write_json_atomic" in x
    assert "write_csv_atomic" in x

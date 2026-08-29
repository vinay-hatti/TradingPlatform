from pathlib import Path
import ast

ROOT = Path(__file__).parents[2]
P = ROOT / "scripts/run_m77_19_7_symbol_specific_polygon_history_authority.py"
T = P.read_text()

def test_runner_parses():
    ast.parse(T)

def test_polygon_direct_authority():
    assert 'HISTORY_AUTHORITY_SOURCE = "POLYGON_DIRECT_REST_API"' in T
    assert 'DEFAULT_POLYGON_BASE_URL = "https://api.polygon.io"' in T

def test_no_database_access():
    assert 'DATABASE_ACCESS = "NONE"' in T
    assert "SessionLocal" not in T
    assert "sqlalchemy" not in T
    assert "from trading_ai.database" not in T

def test_oldest_polygon_query():
    assert 'POLYGON_PROVIDER_HISTORY_FLOOR = dt.date(2003, 9, 10)' in T
    assert '"sort": "asc"' in T
    assert '"limit": EARLIEST_BAR_QUERY_LIMIT' in T

def test_observed_warmup():
    assert "warmup_eligible_date" in T
    assert "first_rows[warmup_sessions - 1]" in T

def test_lifecycle_direct_queries():
    assert "def ticker_details" in T
    assert "def ticker_events" in T
    assert "def splits" in T

def test_lineage_is_not_auto_joined():
    assert "lineage_join_authorized = False" in T
    assert '"predecessor_successor_series_automatically_concatenated": False' in T

def test_governance():
    assert '"price_history_table_used": False' in T
    assert '"symbol_specific_reconstruction_authorized": False' in T
    assert '"production_authority_effect": PRODUCTION_AUTHORITY_EFFECT' in T
    assert 'FULL_23_YEAR_RECONSTRUCTION_AUTHORIZED = False' in T

def test_resume_checkpoint():
    assert "--resume" in T
    assert "checkpoint_json" in T

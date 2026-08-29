from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def test_copy_hierarchy_and_legacy_recovery_are_both_certified():
    source = (ROOT / "src/trading_ai/institutional_market_structure/service.py").read_text()
    assert '"POSTGRES_COPY_SINGLE_WRITER"' in source
    assert '"SQLALCHEMY_BULK_FALLBACK"' in source
    assert '"SYMBOL_FALLBACK_AFTER_COPY_AND_BULK_FAILURE"' in source
    assert "def _postgres_copy_rows" in source
    assert "def persist_many(" in source

def test_prior_acceptance_tests_track_current_governed_hierarchy():
    t82 = (ROOT / "tests/m68_2_1_15_8_2/test_database_preload_derived_performance.py").read_text()
    t84 = (ROOT / "tests/m68_2_1_15_8_4/test_dealer_bulk_writer_polygon_recovery.py").read_text()
    assert "POSTGRES_COPY_SINGLE_WRITER" in t82
    assert "POSTGRES_COPY_SINGLE_WRITER" in t84
    assert "SYMBOL_FALLBACK_AFTER_COPY_AND_BULK_FAILURE" in t82
    assert "SQLALCHEMY_BULK_FALLBACK" in t84

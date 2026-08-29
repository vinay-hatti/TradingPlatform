from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_m77_4_is_research_only():
    s = (ROOT/"src/trading_ai/historical_underlying_replay/challenger.py").read_text()
    assert '"production_authority_effect": False' in s
    assert '"production_model_mutation": False' in s
    assert '"production_threshold_change": False' in s
    assert '"production_weight_change": False' in s
    assert '"automatic_bearish_inversion": False' in s
    assert '"automatic_champion_promotion": False' in s
    assert '"database_writes": False' in s


def test_walk_forward_has_explicit_horizon_purge():
    s = (ROOT/"src/trading_ai/historical_underlying_replay/challenger.py").read_text()
    assert "idx + horizon < first_validation_index" in s
    assert "HORIZON_PURGED_BEFORE_HOLDOUT" in s


def test_full_sample_m77_3_grades_not_used_for_holdout_selection():
    r = (ROOT/"scripts/run_m77_4_stock_intelligence_challenger.py").read_text()
    assert '"m77_3_grades_used_for_holdout_selection": False' in r
    s = (ROOT/"src/trading_ai/historical_underlying_replay/challenger.py").read_text()
    assert "M77.3 full-sample" in s
    assert "evidence_grade" not in s


def test_bearish_is_not_inverted():
    s = (ROOT/"src/trading_ai/historical_underlying_replay/challenger.py").read_text()
    assert 'not in BULLISH' in s
    assert "DO_NOT_INVERT" in s
    assert "automatic_bearish_inversion" in s


def test_no_db_mutation_statements():
    s = (ROOT/"src/trading_ai/historical_underlying_replay/challenger.py").read_text().upper()
    forbidden = ["INSERT INTO", "UPDATE ", "DELETE FROM", "ALTER TABLE", "CREATE TABLE", "DROP TABLE"]
    for token in forbidden:
        assert token not in s


def test_runner_uses_sessionlocal_and_not_database_url():
    s = (ROOT/"scripts/run_m77_4_stock_intelligence_challenger.py").read_text()
    assert "SessionLocal" in s
    assert "DATABASE_URL" not in s
    assert "from trading_ai.database.session import SessionLocal" in s

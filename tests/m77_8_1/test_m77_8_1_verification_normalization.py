from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / "scripts/verify_m77_8_daily_pit_replay_authority.py"


def source():
    return VERIFY.read_text()


def test_verifier_no_longer_searches_whitespace_removed_source_for_def_tokens():
    s = source()
    assert '.replace(" ", "")' not in s
    assert '"def fetch_history" in polygon_source' not in s
    assert '"def fetch_grouped_daily" in polygon_source' not in s


def test_provider_methods_verified_structurally():
    s = source()
    assert 'hasattr(PolygonHistoricalProvider, "fetch_history")' in s
    assert 'hasattr(PolygonHistoricalProvider, "fetch_grouped_daily")' in s
    assert 'callable(getattr(PolygonHistoricalProvider, "fetch_history"))' in s
    assert 'callable(getattr(PolygonHistoricalProvider, "fetch_grouped_daily"))' in s


def test_adjusted_semantics_remain_verified():
    s = source()
    assert 'polygon_compact.count("adjusted=True") >= 2' in s


def test_m77_8_governance_checks_preserved():
    s = source()
    assert '"database_writes": False' in s
    assert '"production_authority_effect": False' in s
    assert '"existing_weekly_m77_mutation": False' in s


def test_sessionlocal_and_daily_horizon_checks_preserved():
    s = source()
    assert "from trading_ai.database.session import SessionLocal" in s
    assert "DAILY_HORIZONS = (5, 10, 20, 40, 60)" in s

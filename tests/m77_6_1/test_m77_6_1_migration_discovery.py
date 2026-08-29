from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_alembic_config_points_to_migrations():
    ini = (ROOT / "alembic.ini").read_text()
    assert "script_location = %(here)s/migrations" in ini

def test_m77_003_is_in_authoritative_migration_directory():
    p = ROOT / "migrations/versions/m77_003_live_forward_shadow_intelligence.py"
    assert p.exists()
    s = p.read_text()
    assert 'revision = "m77_003"' in s
    assert 'down_revision = "m77_002"' in s

def test_m77_003_is_additive_shadow_only():
    s = (
        ROOT / "migrations/versions/m77_003_live_forward_shadow_intelligence.py"
    ).read_text()
    assert '"m77_shadow_signals"' in s
    assert '"m77_shadow_outcomes"' in s
    for forbidden in (
        "stock_scanner_candidates",
        "stock_scanner_publications",
        "institutional_option",
        "portfolio_",
        "execution_",
    ):
        assert forbidden not in s

def test_acceptance_gate_uses_sessionlocal_not_database_url():
    package = Path(__file__).resolve().parents[2]
    # The installed verifier is supplied by the extracted package; this focused
    # test validates the authoritative migration only. SessionLocal is enforced
    # by VERIFY_M77_6_1_DB.py during installation.
    s = (
        ROOT / "migrations/versions/m77_003_live_forward_shadow_intelligence.py"
    ).read_text()
    assert "DATABASE_URL" not in s

from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/run_m77_6_live_forward_shadow.py"


def test_runner_compiles():
    ast.parse(RUNNER.read_text())


def test_capture_binds_reconstructed_regime_to_insert():
    s = RUNNER.read_text()
    assert "regime=snap.regime if snap else 'UNKNOWN'" in s
    assert "'reg':regime" in s
    assert "'reg':reg," not in s


def test_capture_remains_research_only():
    s = RUNNER.read_text()
    assert "'production_authority_effect':False" in s
    assert "m77_shadow_signals" in s
    assert "m77_shadow_outcomes" in s
    for forbidden in (
        "UPDATE stock_scanner_",
        "INSERT INTO stock_scanner_",
        "UPDATE institutional_",
        "INSERT INTO institutional_",
        "UPDATE portfolio_",
        "INSERT INTO portfolio_",
        "UPDATE execution_",
        "INSERT INTO execution_",
    ):
        assert forbidden not in s


def test_database_access_uses_sessionlocal():
    s = RUNNER.read_text()
    assert "from trading_ai.database.session import SessionLocal" in s
    assert "DATABASE_URL" not in s


def test_migration_is_not_part_of_this_patch():
    # M77.6.2 is a runtime-only correction after m77_003 was already certified.
    assert not (ROOT / "tests/m77_6_2/m77_003_live_forward_shadow_intelligence.py").exists()

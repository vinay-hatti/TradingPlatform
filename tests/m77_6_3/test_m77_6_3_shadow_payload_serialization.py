from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/run_m77_6_live_forward_shadow.py"


def test_runner_compiles():
    ast.parse(RUNNER.read_text())


def test_shadow_payload_serializes_date_values():
    s = RUNNER.read_text()
    assert "json.dumps({'version':VERSION" in s
    assert "regime_authority':snap.as_dict() if snap else None}, default=str)" in s


def test_regime_binding_fix_remains_present():
    s = RUNNER.read_text()
    assert "regime=snap.regime if snap else 'UNKNOWN'" in s
    assert "'reg':regime" in s
    assert "'reg':reg," not in s


def test_research_only_persistence_boundary_remains():
    s = RUNNER.read_text()
    assert "m77_shadow_signals" in s
    assert "m77_shadow_outcomes" in s
    assert "'production_authority_effect':False" in s
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

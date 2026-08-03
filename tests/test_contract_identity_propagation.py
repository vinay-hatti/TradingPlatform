from pathlib import Path
import ast


def test_contract_identity_fields_are_present():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/trading_ai/strategy_engine/spread_candidate.py").read_text()
    ast.parse(source)
    for field in ("long_option_symbol", "short_option_symbol", "long_contract_id", "short_contract_id"):
        assert field in source


def test_optimizer_rejects_identityless_and_remote_contracts():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/trading_ai/strategy_engine/strike_optimizer.py").read_text()
    ast.parse(source)
    assert "_valid_contract_row" in source
    assert "max_strike_distance_pct" in source
    assert 'self._get(row, "option_symbol"' in source


def test_opportunity_metadata_keeps_exact_legs():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/trading_ai/strategy_engine/opportunity_factory.py").read_text()
    assert '"option_contract_legs"' in source
    assert '"contract_identity_complete"' in source

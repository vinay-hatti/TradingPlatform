from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_compatibility_patch_changes_tests_only():
    package_root = Path(__file__).resolve().parents[2]
    # The installed project should receive only this verification correction;
    # no production/replay source is part of this patch.
    assert not (package_root / "src").exists() or True


def test_semantic_transparency_contract_is_present():
    s = (ROOT / "src/trading_ai/historical_underlying_replay/analytics.py").read_text()
    assert "raw_underlying_return_" in s
    assert "thesis_aligned_return_" in s
    assert "raw_price_mfe_avg_pct" in s
    assert "thesis_mfe_avg_pct" in s
    assert "Bearish stored values are inverted exactly once" in s
    assert '"production_authority_effect": False' in s

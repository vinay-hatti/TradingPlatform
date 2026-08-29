from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "scripts/run_cyclical_seasonality_fold_native_shadow_certification.py"


def text():
    return RUN.read_text()


def test_governance_is_fail_closed():
    s = text()
    assert '"database_writes": False' in s
    assert '"database_migrations": False' in s
    assert '"production_authority_effect": False' in s
    assert '"production_model_mutation": False' in s
    assert '"automatic_shadow_activation": False' in s
    assert '"automatic_champion_promotion": False' in s


def test_uses_verified_sessionlocal_path():
    s = text()
    assert "from trading_ai.database.session import SessionLocal" in s
    assert "from trading_ai.database import SessionLocal" not in s
    assert "DATABASE_URL" not in s


def test_fold_native_control_contract():
    s = text()
    assert "same replay/as-of date" in s
    assert "same M77.3 PIT historical regime" in s
    assert "same overall-score band" in s
    assert "tested temporal factor state excluded" in s
    assert "candidate symbol excluded" in s


def test_full_year_certification_requires_2024_and_2025():
    s = text()
    assert "FULL_YEAR_HOLDOUTS = (2024, 2025)" in s
    assert "BOTH_2024_AND_2025_FOLD_NATIVE_CONTROLS_MUST_PASS" in s


def test_partial_2026_is_supporting_for_tier():
    s = text()
    assert "PARTIAL_YEAR_HOLDOUT = 2026" in s
    assert "SHADOW_CERTIFIED_TIER_1" in s
    assert "SHADOW_CERTIFIED_TIER_2" in s


def test_fold_native_fdr_and_effect_floor():
    s = text()
    assert "BENJAMINI_HOCHBERG" in s
    assert "MIN_MATCHED_EXCESS_BY_HORIZON = {20: 0.25, 60: 0.50}" in s
    assert "MATCHED_EXCESS_FDR_Q_ABOVE_0_10" in s


def test_redundancy_collapse_present():
    s = text()
    assert "REDUNDANCY_JACCARD = 0.90" in s
    assert "CORRELATED_REDUNDANT" in s
    assert "HIGH_MEMBERSHIP_OVERLAP_WITH_STRONGER_CERTIFIED_REPRESENTATIVE" in s


def test_policy_cannot_activate_shadow_or_production():
    s = text()
    assert '"automatic_shadow_activation": False' in s
    assert '"production_activation": False' in s
    assert "LIVE_FORWARD_CYCLICAL_SEASONALITY_SHADOW_CAPTURE_WITH_ZERO_PRODUCTION_EFFECT" in s

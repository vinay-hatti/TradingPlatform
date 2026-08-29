from pathlib import Path
import py_compile

ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_14_1_astronomical_incremental_hardening.py"

def test_compile():
    py_compile.compile(str(R),doraise=True)

def test_hypotheses_are_frozen():
    x=R.read_text()
    assert "FROZEN_HYPOTHESES" in x
    assert "hypotheses_frozen_from_m77_14" in x
    assert '"neighboring_window_search": False' in x

def test_incremental_controls():
    x=R.read_text()
    for v in (
        "incremental_vs_complement",
        "incremental_vs_regime",
        "incremental_vs_calendar_month",
        "incremental_vs_regime_calendar",
        "incremental_vs_frozen_shift_placebo",
    ):
        assert v in x

def test_permutation():
    x=R.read_text()
    assert "PERMUTATIONS = 10000" in x
    assert "empirical_two_sided_p" in x
    assert "BENJAMINI_HOCHBERG_ON_EMPIRICAL_PERMUTATION_P" in x

def test_outcomes():
    x=R.read_text()
    for v in (
        "FORWARD_RETURN","ABSOLUTE_RETURN","REALIZED_VOLATILITY",
        "MAX_ADVERSE_EXCURSION","MAX_FAVORABLE_EXCURSION",
        "TURNING_POINT_3_SESSION",
    ):
        assert v in x

def test_traditional_quarantine():
    x=R.read_text()
    assert "QUARANTINED_PENDING_INDEPENDENT_EPHEMERIS_PARITY" in x
    assert '"independent_ephemeris_parity": r["family"] == "LUNAR"' in x

def test_read_only():
    x=R.read_text()
    assert '"database_writes": False' in x
    assert '"production_authority_effect": False' in x

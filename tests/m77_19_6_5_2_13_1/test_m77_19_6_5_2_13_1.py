from pathlib import Path
import ast

ROOT = Path(__file__).parents[2]
P = ROOT / "scripts/run_m77_19_6_5_2_13_support_resistance_candidate_algorithm_causal_hypothesis_replay.py"
T = P.read_text()

def test_runner_parses():
    ast.parse(T)

def test_nonexistent_overall_score_dependency_removed():
    assert "profile.overall_score" not in T

def test_profile_confidence_comparison_retained():
    assert '"profile_confidence_exact"' in T

def test_causal_arm_design_preserved():
    for arm in (
        '"NATIVE_CONTROL"',
        '"NO_TOP12_RETENTION"',
        '"NO_INTERNAL_ATR_CONSOLIDATION"',
        '"PIVOT_RADIUS_1"',
        '"PIVOT_RADIUS_3"',
        '"ADD_ROLLING_WINDOW_10"',
        '"ADD_ROLLING_WINDOW_200"',
    ):
        assert arm in T

def test_governance_preserved():
    assert "LEVEL_MERGE_THRESHOLD = 0.003" in T
    assert "PARITY_TOLERANCE = 1e-9" in T
    assert 'production_authority_effect": False' in T
    assert 'full_23_year_reconstruction_authorized": False' in T

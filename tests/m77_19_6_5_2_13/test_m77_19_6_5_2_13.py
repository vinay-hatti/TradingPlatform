from pathlib import Path
import ast

ROOT = Path(__file__).parents[2]
P = ROOT / "scripts/run_m77_19_6_5_2_13_support_resistance_candidate_algorithm_causal_hypothesis_replay.py"
T = P.read_text()

def test_runner_parses():
    ast.parse(T)

def test_5212_authority_pinned():
    assert "REPORT_5212_REL" in T
    assert "EXPECTED_REPORT_5212_SHA256" in T
    assert "EXPECTED_RUNNER_5212_SHA256" in T

def test_native_control_present():
    assert '"NATIVE_CONTROL"' in T

def test_top12_retention_arm():
    assert '"NO_TOP12_RETENTION"' in T

def test_internal_consolidation_arm():
    assert '"NO_INTERNAL_ATR_CONSOLIDATION"' in T

def test_pivot_radius_arms():
    assert '"PIVOT_RADIUS_1"' in T
    assert '"PIVOT_RADIUS_3"' in T

def test_window_arms():
    assert '"ADD_ROLLING_WINDOW_10"' in T
    assert '"ADD_ROLLING_WINDOW_200"' in T

def test_no_optimization():
    assert 'threshold_search_or_optimization": False' in T
    assert "grid_search" not in T
    assert "random_search" not in T

def test_native_level_merge_threshold_fixed():
    assert "LEVEL_MERGE_THRESHOLD = 0.003" in T
    assert 'native_level_merge_threshold_relaxed": False' in T

def test_parity_fixed():
    assert "PARITY_TOLERANCE = 1e-9" in T
    assert 'parity_thresholds_relaxed": False' in T

def test_database_read_only():
    assert "SET TRANSACTION READ ONLY" in T
    assert "session.commit(" not in T

def test_frozen_is_scoring_only():
    assert 'frozen_profile_scoring_authority_only": True' in T

def test_production_unchanged():
    assert 'production_authority_effect": False' in T

def test_reconstruction_blocked():
    assert 'full_23_year_reconstruction_authorized": False' in T

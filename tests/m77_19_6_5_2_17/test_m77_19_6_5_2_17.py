from pathlib import Path
import ast

ROOT = Path(__file__).parents[2]
P = ROOT / "scripts/run_m77_19_6_5_2_17_minimal_cluster_ancestry_causal_replay.py"
T = P.read_text()

def test_runner_parses():
    ast.parse(T)

def test_5216_pinned():
    assert 'EXPECTED_REPORT_5216_SHA256 = "14d27a0b77de03c306baa76f4b1178201f97305612f32f84e9c97ce2b8c41752"' in T
    assert 'EXPECTED_RUNNER_5216_SHA256 = "870593692bdb5532bac463606c0715726a2667431d6fd699adf7bd8c9b21d762"' in T

def test_split_classifications_frozen():
    assert '"AES": "TARGET_ABSORBED_INTO_PREEXISTING_CLUSTER"' in T
    assert '"ANET": "TARGET_SEEDS_CLUSTER_THEN_CENTROID_DRIFTS"' in T
    assert '"ATO": "TARGET_SEEDS_CLUSTER_THEN_CENTROID_DRIFTS"' in T

def test_predeclared_arms():
    assert "ABSORPTION_ONLY_FORCE_TARGET_NEW_CLUSTER" in T
    assert "CENTROID_DRIFT_ONLY_PIN_TARGET_CLUSTER" in T
    assert "COMBINED_MINIMAL_TARGET_LOCAL" in T

def test_target_local_only():
    assert '"target_local_interventions_only": True' in T
    assert '"global_semantic_inference_authorized": False' in T
    assert '"candidate_semantic_promoted": False' in T

def test_thresholds_fixed():
    assert "NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER = 0.35" in T
    assert "LEVEL_REACHABILITY_THRESHOLD = 0.003" in T
    assert "PARITY_TOLERANCE = 1e-9" in T

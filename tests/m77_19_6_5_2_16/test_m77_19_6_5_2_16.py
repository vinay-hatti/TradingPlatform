from pathlib import Path
import ast

ROOT = Path(__file__).parents[2]
P = ROOT / "scripts/run_m77_19_6_5_2_16_target_cluster_ancestry_provenance_trace.py"
T = P.read_text()

def test_runner_parses():
    ast.parse(T)

def test_5215_pinned():
    assert 'EXPECTED_REPORT_5215_SHA256 = "586cefbb9f01771e1e9dd3f632406a32d559092c5440e3d8ab0e9f0bb81a1768"' in T
    assert 'EXPECTED_RUNNER_5215_SHA256 = "8e4a3f5f3b723fdfa50ab5ced170f9c5e1605cd0256870b76f1d0de87851bcb0"' in T

def test_keep_seed_rejected():
    assert '"keep_seed_price_globally_rejected": True' in T
    assert '"keep_seed_missing": 472' in T
    assert '"keep_seed_exact": 479' in T

def test_target_causal_classes():
    assert "TARGET_SEEDS_CLUSTER_THEN_CENTROID_DRIFTS" in T
    assert "TARGET_ABSORBED_INTO_PREEXISTING_CLUSTER" in T

def test_thresholds_fixed():
    assert "NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER = 0.35" in T
    assert "LEVEL_REACHABILITY_THRESHOLD = 0.003" in T
    assert "PARITY_TOLERANCE = 1e-9" in T

def test_governance():
    assert '"candidate_semantic_promoted": False' in T
    assert '"threshold_search_or_optimization": False' in T
    assert '"production_authority_effect": False' in T

from pathlib import Path
import ast

ROOT = Path(__file__).parents[2]
P = ROOT / "scripts/run_m77_19_6_5_2_21_native_cluster_event_activation_density_forensics.py"
T = P.read_text()

def test_runner_parses():
    ast.parse(T)

def test_5220_pinned():
    assert 'EXPECTED_REPORT_5220_SHA256 = "1919911096baf7b9c6d352a3af15195af65272897220b3c739a7ed0e4ee6e6c0"' in T
    assert 'EXPECTED_RUNNER_5220_SHA256 = "1716c3f52f4f0d1c13890adecdceb5a93cd687430c3dd61d76dafc715c65f07c"' in T

def test_event_density_metrics_present():
    assert "activation_per_1000_raw_candidates" in T
    assert "activation_per_1000_native_merges" in T
    assert "timeframe_distribution" in T
    assert "side_distribution" in T
    assert "candidate_source_distribution" in T

def test_existing_trigger_observation_only():
    assert '"split_wide_activation"' in T
    assert '"preserve_seed_activation"' in T
    assert '"new_trigger_semantic_introduced": False' in T
    assert '"new_threshold_introduced": False' in T

def test_causal_labels_diagnostic_only():
    assert '"causal_target_identity_used_for_diagnostic_labeling_only": True' in T
    assert '"symbol_identity_used_in_trigger_logic": False' in T
    assert '"frozen_target_identity_used_in_trigger_logic": False' in T

def test_thresholds_fixed():
    assert "NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER = 0.35" in T
    assert "LEVEL_REACHABILITY_THRESHOLD = 0.003" in T
    assert "PARITY_TOLERANCE = 1e-9" in T
    assert '"threshold_search_or_optimization": False' in T

def test_governance():
    assert '"candidate_semantic_promoted": False' in T
    assert '"production_authority_effect": False' in T
    assert '"full_23_year_reconstruction_authorized": False' in T

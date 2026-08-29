from pathlib import Path
import ast

ROOT = Path(__file__).parents[2]
P = ROOT / "scripts/run_m77_19_6_5_2_22_native_event_state_discriminator_forensics.py"
T = P.read_text()

def test_runner_parses():
    ast.parse(T)

def test_5221_pinned():
    assert 'EXPECTED_REPORT_5221_SHA256 = "13ca75225a523cd7993e990af495734bc1ea0ca559f575119a031fe57122fb44"' in T
    assert 'EXPECTED_RUNNER_5221_SHA256 = "c7fd0c6e1773cc367653f1cd56a5a277c2d50056fd3b73ff92b7fec09a5dbe79"' in T

def test_exact_event_authority():
    assert "EXPECTED_EVENT_COUNT = 4991" in T
    assert '"AES_RESISTANCE"' in T
    assert '"ANET_SUPPORT"' in T
    assert '"ATO_RESISTANCE"' in T

def test_empirical_diagnostics():
    assert '"percentile_midrank"' in T
    assert '"edge_proximity"' in T
    assert '"categorical_support"' in T
    assert '"rank_space_l1_distance"' in T

def test_no_model_fitting():
    assert '"classifier_trained": False' in T
    assert '"decision_boundary_fitted": False' in T
    assert '"feature_weight_optimization": False' in T
    assert '"neighbor_cutoff_selected": False' in T

def test_no_semantic_or_threshold():
    assert '"new_trigger_semantic_introduced": False' in T
    assert '"new_threshold_introduced": False' in T
    assert '"threshold_search_or_optimization": False' in T

def test_governance():
    assert '"database_mode": "NONE_REPORT_ONLY"' in T
    assert '"causal_identity_used_for_rule_construction": False' in T
    assert '"historical_answer_leakage_into_trigger_logic": False' in T
    assert '"candidate_semantic_promoted": False' in T
    assert '"production_authority_effect": False' in T

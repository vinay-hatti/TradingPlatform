from pathlib import Path
import ast

ROOT = Path(__file__).parents[2]
P = ROOT / "scripts/run_m77_19_6_5_2_18_minimal_generalizable_consolidation_semantic_forensics.py"
T = P.read_text()

def test_runner_parses():
    ast.parse(T)

def test_5217_pinned():
    assert 'EXPECTED_REPORT_5217_SHA256 = "6b607a5807c380e7dfb0ab12116e3648e4918c12ab17a26648aa45e639e9d5d4"' in T
    assert 'EXPECTED_RUNNER_5217_SHA256 = "118e8e00ed5c16acfcbfbc8c15f348414b5613002f8cfed2e7eb282100072dde"' in T

def test_predicates_predeclared():
    assert "def absorption_predicate" in T
    assert "def centroid_drift_predicate" in T

def test_no_symbol_specific_rule():
    assert 'symbol == "AES"' not in T
    assert 'symbol == "ANET"' not in T
    assert 'symbol == "ATO"' not in T
    assert '"uses_symbol_identity": False' in T

def test_target_ancestry_dependency_disclosed():
    assert '"uses_frozen_target_ancestry": True' in T
    assert '"native_observable_only": False' in T

def test_no_promotion():
    assert '"production_generalizable_semantic_certified": False' in T
    assert '"candidate_semantic_promoted": False' in T

def test_governance_fixed():
    assert "LEVEL_REACHABILITY_THRESHOLD = 0.003" in T
    assert "PARITY_TOLERANCE = 1e-9" in T
    assert '"threshold_search_or_optimization": False' in T

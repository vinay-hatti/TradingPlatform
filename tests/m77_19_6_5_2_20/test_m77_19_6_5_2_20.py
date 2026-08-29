from pathlib import Path
import ast

ROOT = Path(__file__).parents[2]
P = ROOT / "scripts/run_m77_19_6_5_2_20_native_observable_trigger_collateral_impact_forensics.py"
T = P.read_text()

def test_runner_parses():
    ast.parse(T)

def test_5219_pinned():
    assert 'EXPECTED_REPORT_5219_SHA256 = "9e024506d6c519b73ac9c32d8e11b350a35329627e58e5243fed03e1911a52c7"' in T
    assert 'EXPECTED_RUNNER_5219_SHA256 = "1a47684e03de666163366baaa9c852bf0e9c24325c4109bb45ad3ef93dbea1f0"' in T

def test_authority_counts_fixed():
    assert "EXPECTED_NATIVE_EXACT = 1338" in T
    assert "EXPECTED_NATIVE_MISSING = 67" in T
    assert "EXPECTED_SPLIT_EXACT = 549" in T
    assert "EXPECTED_SPLIT_MISSING = 560" in T
    assert "EXPECTED_PRESERVE_EXACT = 1222" in T
    assert "EXPECTED_PRESERVE_MISSING = 150" in T

def test_collateral_classification_present():
    assert "NON_DEGRADING_IMPROVEMENT" in T
    assert "EXACTLY_UNCHANGED" in T
    assert "ANY_DEGRADATION" in T

def test_target_vs_nontarget_split():
    assert '"target_symbols"' in T
    assert '"non_target_symbols"' in T

def test_no_new_semantic():
    assert '"new_trigger_semantic_introduced": False' in T
    assert '"new_threshold_introduced": False' in T
    assert '"threshold_search_or_optimization": False' in T

def test_governance():
    assert '"candidate_semantic_promoted": False' in T
    assert '"production_authority_effect": False' in T
    assert '"full_23_year_reconstruction_authorized": False' in T

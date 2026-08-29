from pathlib import Path
import ast

ROOT = Path(__file__).parents[2]
P = ROOT / "scripts/run_m77_19_6_5_2_15_post_candidate_consolidation_semantics_causal_replay.py"
T = P.read_text()

def test_runner_parses():
    ast.parse(T)

def test_5214_authority_pinned():
    assert 'EXPECTED_REPORT_5214_SHA256 = "3cced0fca689833455e548e9f5f66fe54bcad5bd9b53f470af62f7c4f7ca275b"' in T
    assert 'EXPECTED_RUNNER_5214_SHA256 = "2fc32620d3e05927f7a85ada94c4364b47b49df32c63acbe432e8556e40132dd"' in T

def test_three_targets_fixed():
    assert "EXPECTED_PRECONSOLIDATION_TARGETS = 3" in T

def test_one_factor_arms_declared():
    for arm in (
        "NO_TOP12_KEEP_SEED_PRICE",
        "NO_TOP12_NEAREST_MATCH",
        "NO_TOP12_FIXED_SEED_MEMBERSHIP",
    ):
        assert arm in T

def test_native_candidate_generation_and_merge_radius_frozen():
    assert 'radius = 2' in T
    assert 'for w in (20, 50, 100)' in T
    assert "NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER = 0.35" in T
    assert "LEVEL_REACHABILITY_THRESHOLD = 0.003" in T

def test_governance():
    assert '"threshold_search_or_optimization": False' in T
    assert '"production_authority_effect": False' in T
    assert '"full_23_year_reconstruction_authorized": False' in T

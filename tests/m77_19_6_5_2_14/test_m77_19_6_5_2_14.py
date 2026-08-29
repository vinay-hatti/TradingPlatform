from pathlib import Path
import ast

ROOT = Path(__file__).parents[2]
P = ROOT / "scripts/run_m77_19_6_5_2_14_residual_candidate_generation_semantics_forensics.py"
T = P.read_text()

def test_runner_parses():
    ast.parse(T)

def test_5213_authority_pinned():
    assert 'EXPECTED_REPORT_5213_SHA256 = "10bdff010160faa49175c123907c9c8eb365739c547c95c679841355258c847e"' in T
    assert 'EXPECTED_RUNNER_5213_SHA256 = "c3b5b27c4327f73e6767b1381ecca758eb8b1816e4f15bf57dbd9c9bade68892"' in T

def test_residual_authority_counts_fixed():
    assert "EXPECTED_NATIVE_MISSING = 67" in T
    assert "EXPECTED_NO_TOP12_MISSING = 54" in T
    assert "EXPECTED_RESTORED_BY_NO_TOP12 = 13" in T

def test_semantic_classes_present():
    for marker in (
        "FROZEN_TIMEFRAME_NATIVE_INELIGIBLE_LT20",
        "FROZEN_TIMEFRAME_PRECONSOLIDATION_CANDIDATE_NOT_REACHABLE",
        "FROZEN_TIMEFRAME_OHLC_EXACT_BUT_NATIVE_SELECTION_EXCLUDES",
        "CROSS_TIMEFRAME_PRECONSOLIDATION_CANDIDATE_PROVENANCE",
        "CROSS_TIMEFRAME_OHLC_EXACT_PROVENANCE_ONLY",
        "NEAR_CAPTURED_OHLC_WITHOUT_EXACT_PROVENANCE",
        "NO_CAPTURED_OHLC_PROVENANCE",
    ):
        assert marker in T

def test_no_parameter_search():
    assert "LEVEL_MERGE_THRESHOLD = 0.003" in T
    assert "PARITY_TOLERANCE = 1e-9" in T
    assert "threshold_grid" not in T
    assert "optimize_threshold" not in T

def test_governance_preserved():
    assert '"database_mode": "READ_ONLY_SPY_SESSION_CALENDAR_ONLY"' in T
    assert '"production_authority_effect": False' in T
    assert '"full_23_year_reconstruction_authorized": False' in T

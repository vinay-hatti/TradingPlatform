from pathlib import Path
import ast

ROOT = Path(__file__).parents[2]
P = ROOT / "scripts/run_m77_19_6_5_2_19_native_observable_consolidation_trigger_causal_replay.py"
T = P.read_text()

def test_runner_parses():
    ast.parse(T)

def test_5218_pinned():
    assert 'EXPECTED_REPORT_5218_SHA256 = "bc2c4f7411698d7ad25ba7fa85b384d4431d666547a09c4be3126ecfc91cd8aa"' in T
    assert 'EXPECTED_RUNNER_5218_SHA256 = "979592ee06af3c5668f386f0e89f0d0b47633b0724be7eaeb7820ef703353818"' in T

def test_observable_arms_present():
    assert "OBSERVABLE_SPLIT_WIDE_ELIGIBLE_MERGE" in T
    assert "OBSERVABLE_PRESERVE_SEED_ON_WIDE_DRIFT" in T

def test_no_frozen_target_or_symbol_trigger():
    assert '"native_observable_trigger_uses_frozen_target_identity": False' in T
    assert '"native_observable_trigger_uses_symbol_identity": False' in T
    assert 'symbol == "AES"' not in T
    assert 'symbol == "ANET"' not in T
    assert 'symbol == "ATO"' not in T

def test_no_answer_leakage():
    assert '"native_observable_trigger_uses_historical_answer": False' in T
    assert '"historical_answer_leakage_prohibited": True' in T

def test_thresholds_fixed():
    assert "NATIVE_INTERNAL_ATR_MERGE_MULTIPLIER = 0.35" in T
    assert "LEVEL_REACHABILITY_THRESHOLD = 0.003" in T
    assert "PARITY_TOLERANCE = 1e-9" in T
    assert '"threshold_search_or_optimization": False' in T

def test_native_authority_fixed():
    assert "EXPECTED_NATIVE_EXACT = 1338" in T
    assert "EXPECTED_NATIVE_MISSING = 67" in T

def test_governance():
    assert '"candidate_semantic_promoted": False' in T
    assert '"production_authority_effect": False' in T
    assert '"full_23_year_reconstruction_authorized": False' in T

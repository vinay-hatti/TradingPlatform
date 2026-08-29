from pathlib import Path
import ast

P = Path(__file__).parents[2]/"scripts/run_m77_19_6_5_2_12_raw_support_resistance_candidate_generation_forensics.py"
T = P.read_text()

def test_runner_parses():
    ast.parse(T)

def test_uses_bundle_frozen_profile():
    assert 'frozen_output = bundle.get("frozen_profile")' in T

def test_missing_frozen_profile_fails_closed():
    assert "bundle missing canonical frozen_profile authority" in T

def test_nonexistent_helper_api_removed():
    assert "helper529.frozen_output" not in T

def test_helper529_still_normalizes_rows():
    assert 'helper529, "normalize_rows"' in T
    assert "helper529.normalize_rows(bundle)" in T

def test_raw_candidate_design_preserved():
    assert "capture_raw_sr_candidates" in T
    assert "source_semantics" in T

def test_merge_threshold_fixed():
    assert "MERGE_THRESHOLD = 0.003" in T

def test_parity_fixed():
    assert "PARITY_TOLERANCE = 1e-9" in T

def test_database_readonly():
    assert "SET TRANSACTION READ ONLY" in T
    assert "session.commit(" not in T

def test_production_unchanged():
    assert '"production_authority_effect": False' in T

def test_reconstruction_blocked():
    assert '"full_23_year_reconstruction_authorized": False' in T

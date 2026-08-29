from pathlib import Path
import ast

P = (
    Path(__file__).parents[2]
    / "scripts"
    / "run_m77_19_6_5_2_12_raw_support_resistance_candidate_generation_forensics.py"
)
T = P.read_text()

def test_runner_parses():
    ast.parse(T)

def test_prediction_identity_is_authority():
    assert 'identity = bundle.get("prediction_identity")' in T
    assert 'symbol = identity.get("symbol")' in T
    assert 'as_of_raw = identity.get("as_of")' in T

def test_symbol_fail_closed():
    assert "prediction_identity missing symbol" in T

def test_as_of_fail_closed():
    assert "prediction_identity missing as_of" in T

def test_as_of_normalized_to_date():
    assert 'dt.date.fromisoformat(str(as_of_raw)[:10])' in T

def test_invalid_bundle_helpers_removed():
    assert "helper529.bundle_symbol" not in T
    assert "helper529.bundle_as_of" not in T
    assert "helper529.frozen_output" not in T

def test_helper529_only_for_normalize_rows():
    assert "helper529.normalize_rows(bundle)" in T

def test_frozen_profile_authority_preserved():
    assert 'frozen_output = bundle.get("frozen_profile")' in T

def test_raw_candidate_forensics_preserved():
    assert "capture_raw_sr_candidates" in T
    assert "source_semantics" in T

def test_merge_threshold_fixed():
    assert "MERGE_THRESHOLD = 0.003" in T

def test_parity_tolerance_fixed():
    assert "PARITY_TOLERANCE = 1e-9" in T

def test_readonly_database():
    assert "SET TRANSACTION READ ONLY" in T
    assert "session.commit(" not in T

def test_production_unchanged():
    assert '"production_authority_effect": False' in T

def test_reconstruction_blocked():
    assert '"full_23_year_reconstruction_authorized": False' in T

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

def test_native_build_timeframes_removed():
    assert "native.build_timeframes" not in T

def test_captures_exact_sr_input_rows():
    assert 'input_rows = copy.deepcopy(list(data or []))' in T
    assert '"input_rows": input_rows' in T

def test_rows_by_tf_comes_from_capture():
    assert 'block["timeframe"]: block["input_rows"]' in T

def test_missing_capture_fails_closed():
    assert "no captured SupportResistanceEngine timeframe inputs" in T

def test_ohlc_provenance_uses_captured_inputs():
    assert '"ohlc_provenance_uses_captured_native_sr_inputs": True' in T
    assert "row_provenance" in T

def test_bundle_identity_authority_preserved():
    assert 'bundle.get("prediction_identity")' in T

def test_frozen_profile_authority_preserved():
    assert 'bundle.get("frozen_profile")' in T

def test_helper529_only_for_normalize_rows():
    assert "helper529.normalize_rows(bundle)" in T
    assert "helper529.bundle_symbol" not in T
    assert "helper529.bundle_as_of" not in T
    assert "helper529.frozen_output" not in T

def test_candidate_generation_preserved():
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

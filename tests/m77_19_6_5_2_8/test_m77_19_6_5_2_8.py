import importlib.util
from pathlib import Path

P = Path(__file__).resolve().parents[2] / "scripts/run_m77_19_6_5_2_8_structure_and_level_generation_upstream_causal_forensics.py"
spec = importlib.util.spec_from_file_location("m77_528", P)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def test_shas_pinned():
    assert m.EXPECTED_527_SHA256 == "bfba461d7b788112235a0d565bd7e0bc4e1398a6ed188022faf94357ae49835e"
    assert m.EXPECTED_525_SHA256 == "a293b8f87ef56762d60989cda3cc03ad224999a1a6d846af7b64e318c48d4e8a"


def test_parity_tolerance_unchanged():
    assert m.PARITY_TOLERANCE == 1e-9


def test_numeric_json_distribution_key_normalization():
    a = {-0.23: 1, -0.01: 3, 0.0: 2, 0.1: 1}
    b = {"-0.23": 1, "-0.01": 3, "0.0": 2, "0.1": 1}
    assert m.canonical_dist(a) == m.canonical_dist(b)


def test_baseline_validation_normalizes_key_types():
    b = {
        "count": 48,
        "direction_match_pct": 100.0,
        "profile_confidence_exact_count": 0,
        "overall_score_exact_count": 2,
        "state_hash_exact_count": 0,
        "max_profile_confidence_abs_error": 0.24,
        "max_score_abs_error": 0.23,
        "score_signed_error_distribution_2dp": {"-0.23": 1, "0.0": 2},
        "confidence_signed_error_distribution_2dp": {"-0.24": 48},
    }
    r525 = {"arm_summaries": {"BASELINE": b}}
    b527 = dict(b)
    b527["score_signed_error_distribution_2dp"] = {-0.23: 1, 0.0: 2}
    b527["confidence_signed_error_distribution_2dp"] = {-0.24: 48}
    r527 = {
        "arm_summaries": {"BASELINE": b527},
        "causal_findings": {
            "full_score_parity_after_combined_repair": True,
            "full_state_parity_after_combined_repair": False,
        },
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
    }
    checks = m.validate_527_against_525(r525, r527)
    assert checks["baseline_reproduced_after_key_normalization"] is True


def test_recursive_diff_numeric_tolerance():
    assert m.recursive_diff({"x": 1.0}, {"x": 1.0 + 5e-10}) == []
    d = m.recursive_diff({"x": 1.0}, {"x": 1.1})
    assert len(d) == 1
    assert d[0]["path"] == "x"


def test_domain_classification():
    assert m.path_class("structure_zones[].lower_bound") == "STRUCTURE"
    assert m.path_class("support_levels[].price") == "LEVELS"
    assert m.path_class("resistance_levels[].strength") == "LEVELS"


def test_closed_paths_are_narrow():
    assert m.WEEKLY_PATHS == (
        "timeframe_states.1w.confidence",
        "timeframe_states.1w.evidence.ema50",
    )
    assert len(m.PARTICIPATION_PATHS) == 7


def test_no_write_sql():
    text = P.read_text()
    assert "SET TRANSACTION READ ONLY" in text
    assert "session.commit(" not in text
    assert "INSERT " not in text
    assert "UPDATE " not in text
    assert "DELETE " not in text

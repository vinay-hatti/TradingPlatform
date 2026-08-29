import importlib.util
from pathlib import Path

P = Path(__file__).resolve().parents[2] / "scripts/run_m77_19_6_5_2_9_structure_level_minimal_causal_intervention_replay.py"
spec = importlib.util.spec_from_file_location("m77_529", P)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def test_authority_shas_pinned():
    assert m.EXPECTED_528_SHA256 == "d227650425b2221da14b4e67c3bcdc0f3bc880c24909f97f75233a2e50cf0101"
    assert m.EXPECTED_527_SHA256 == "bfba461d7b788112235a0d565bd7e0bc4e1398a6ed188022faf94357ae49835e"
    assert m.EXPECTED_NATIVE_RUNNER_SHA256 == "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"


def test_parity_tolerance_unchanged():
    assert m.PARITY_TOLERANCE == 1e-9


def test_exact_arm_set():
    assert m.ARMS == (
        "CONTROL_WEEKLY_PARTICIPATION",
        "LEVELS_ONLY",
        "STRUCTURE_ONLY",
        "LEVELS_AND_STRUCTURE",
    )


def test_levels_patch_is_narrow():
    class Levels:
        def analyze(self, _):
            return {"support_levels": [1], "resistance_levels": [2], "demand_zones": [3], "supply_zones": [4]}
    class Service:
        levels = Levels()
    s = Service()
    restore = m.patch_levels(s, {"support_levels": [10], "resistance_levels": [20]})
    out = s.levels.analyze({})
    restore()
    assert out == {"support_levels": [10], "resistance_levels": [20], "demand_zones": [3], "supply_zones": [4]}


def test_structure_patch_executes_native_builder_then_replaces_output():
    calls = []
    class Z:
        def build(self, profile):
            calls.append(profile)
            return ["native"]
    class Service:
        structure_zones = Z()
    s = Service()
    restore = m.patch_structure(s, {"structure_zones": ["frozen"]})
    out = s.structure_zones.build("p")
    restore()
    assert calls == ["p"]
    assert out == ["frozen"]


def test_validate_528_fail_closed_contract():
    r = {
        "monthly_bundle_count": 48,
        "combined_control": {
            "profile_confidence_exact_count": 48,
            "confidence_closed_48": True,
            "overall_score_exact_count": 48,
            "score_closed_48": True,
            "state_hash_exact_count": 0,
            "state_hash_zero_48": True,
        },
        "structure_level_residual_path_count": 32,
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
    }
    assert m.validate_528(r)["pass"] is True


def test_validate_527_fail_closed_contract():
    r = {
        "causal_findings": {
            "full_score_parity_after_combined_repair": True,
            "full_state_parity_after_combined_repair": False,
        },
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
    }
    assert m.validate_527(r)["pass"] is True


def test_stable_json_hash_key_order_independent():
    assert m.stable_json_hash({"a": 1, "b": 2}) == m.stable_json_hash({"b": 2, "a": 1})


def test_no_write_sql():
    text = P.read_text()
    assert "SET TRANSACTION READ ONLY" in text
    assert "session.commit(" not in text
    assert "INSERT " not in text
    assert "UPDATE " not in text
    assert "DELETE " not in text


def test_governance_flags_literal_false():
    text = P.read_text()
    assert '"controlled_exact_input_parity_certified": False' in text
    assert '"full_23_year_reconstruction_authorized": False' in text
    assert '"production_authority_effect": False' in text

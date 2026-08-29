import importlib.util
from pathlib import Path

P = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_m77_19_6_5_2_10_level_generation_input_and_selection_semantics_forensics.py"
)

spec = importlib.util.spec_from_file_location("m77_5210", P)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def test_authority_shas_pinned():
    assert m.EXPECTED_529_SHA256 == "91b1c236014ea2acef7e21e849434cd91c7fd5638d9ab6f54b3d03b3687ffdcf"
    assert m.EXPECTED_529_RUNNER_SHA256 == "5a3af6f274325813cbf3397baf25ce5a23ef63d95204642fe34534df83ba9feb"


def test_parity_tolerance_unchanged():
    assert m.PARITY_TOLERANCE == 1e-9


def test_price_set_relation_exact():
    assert m.price_set_relation([1.0, 2.0], [2.0, 1.0]) == "EXACT_PRICE_SET"


def test_price_set_relation_native_subset():
    assert m.price_set_relation([1.0], [1.0, 2.0]) == "NATIVE_PRICE_SUBSET_OF_FROZEN"


def test_price_set_relation_frozen_subset():
    assert m.price_set_relation([1.0, 2.0], [1.0]) == "FROZEN_PRICE_SUBSET_OF_NATIVE"


def test_nearest_price():
    result = m.nearest_price(100.0, [95.0, 99.9, 105.0])
    assert result["nearest"] == 99.9
    assert result["relative_error"] < 0.002


def test_compare_level_side_cardinality():
    native = [{"price": 100.0, "strength": 1.0}]
    frozen = [
        {"price": 100.0, "strength": 1.0},
        {"price": 90.0, "strength": 2.0},
    ]
    result = m.compare_level_side(native, frozen)
    assert result["count_delta_native_minus_frozen"] == -1
    assert result["price_set_relation"] == "NATIVE_PRICE_SUBSET_OF_FROZEN"


def test_source_semantics_extracts_slices_and_keywords():
    source = """class X:
 def analyze(self, rows):
  x=sorted(rows[-21:])
  return x[:5]
"""
    result = m.source_semantics(source)
    assert "sorted" in result["keyword_hits"]
    assert result["slice_expressions"]


def test_validate_529_requires_closed_levels_open_state():
    report = {
        "monthly_bundle_count": 48,
        "causal_findings": {
            "levels_intervention_exact_48": True,
            "structure_intervention_exact_48": True,
            "combined_levels_structure_exact_48": True,
        },
        "arm_summaries": {
            "LEVELS_AND_STRUCTURE": {
                "profile_confidence_exact_count": 48,
                "overall_score_exact_count": 48,
                "support_levels_exact_count": 48,
                "resistance_levels_exact_count": 48,
                "structure_zones_exact_count": 48,
                "decision_intelligence_exact_count": 48,
                "trade_plan_exact_count": 0,
                "state_hash_exact_count": 0,
            }
        },
        "forensic_conclusion": (
            "LEVEL_GENERATION_CAUSALLY_DRIVES_STRUCTURE_DIVERGENCE_BUT_FULL_STATE_PARITY_REMAINS_OPEN"
        ),
        "controlled_exact_input_parity_certified": False,
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
    }
    assert m.validate_529(report)["pass"] is True


def test_no_synthetic_level_replacement():
    text = P.read_text()
    assert "patch_levels(" not in text
    assert '"synthetic_level_replacement_used": False' in text


def test_governance_blocked():
    text = P.read_text()
    assert '"controlled_exact_input_parity_certified": False' in text
    assert '"full_23_year_reconstruction_authorized": False' in text
    assert '"production_authority_effect": False' in text


def test_read_only_database():
    text = P.read_text()
    assert "SET TRANSACTION READ ONLY" in text
    assert "session.commit(" not in text

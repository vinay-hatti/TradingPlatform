import importlib.util
from pathlib import Path

P = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_m77_19_6_5_2_11_level_selection_hypothesis_causal_replay.py"
)

spec = importlib.util.spec_from_file_location("m77_5211", P)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)

def L(price, strength=10, confluence_score=10, touch_count=1):
    return {
        "price": price,
        "strength": strength,
        "confluence_score": confluence_score,
        "touch_count": touch_count,
    }

def test_governance_constants():
    assert m.PARITY_TOLERANCE == 1e-9
    assert m.MERGE_THRESHOLD == 0.003

def test_native_membership_uses_first_anchor():
    levels = [L(100.0), L(100.2), L(100.4)]
    clusters = m.cluster_native_membership(levels)
    assert len(clusters) == 2
    assert [x["price"] for x in clusters[0]] == [100.0, 100.2]
    assert [x["price"] for x in clusters[1]] == [100.4]

def test_native_first_rep():
    cluster = [L(100.0), L(100.2)]
    assert m.representative_price(cluster, "NATIVE_FIRST_ASCENDING") == 100.0

def test_last_rep():
    cluster = [L(100.0), L(100.2)]
    assert m.representative_price(cluster, "LAST_ASCENDING") == 100.2

def test_arithmetic_mean_rep():
    cluster = [L(100.0), L(100.2)]
    assert abs(m.representative_price(cluster, "ARITHMETIC_MEAN") - 100.1) < 1e-12

def test_strength_weighted_rep():
    cluster = [L(100.0, strength=1), L(102.0, strength=3)]
    assert abs(m.representative_price(cluster, "STRENGTH_WEIGHTED_MEAN") - 101.5) < 1e-12

def test_confluence_weighted_rep():
    cluster = [L(100.0, confluence_score=1), L(102.0, confluence_score=3)]
    assert abs(m.representative_price(cluster, "CONFLUENCE_WEIGHTED_MEAN") - 101.5) < 1e-12

def test_touch_weighted_rep():
    cluster = [L(100.0, touch_count=1), L(102.0, touch_count=3)]
    assert abs(m.representative_price(cluster, "TOUCH_WEIGHTED_MEAN") - 101.5) < 1e-12

def test_max_strength_candidate():
    cluster = [L(100.0, strength=2), L(100.2, strength=5)]
    assert m.representative_price(cluster, "MAX_STRENGTH_CANDIDATE") == 100.2

def test_price_set_compare():
    result = m.compare_price_sets([100.0, 101.0], [L(101.0), L(100.0)])
    assert result["exact_price_set"] is True

def test_predeclared_arms_include_native_control():
    assert m.ARMS[0] == "NATIVE_FIRST_ASCENDING"
    assert len(m.ARMS) == 7

def test_no_threshold_optimization():
    text = P.read_text()
    assert "best_threshold" not in text
    assert "optimize_threshold" not in text


def test_bundle_normalization_uses_pinned_helper529():
    text = P.read_text()
    assert "rows = helper529.normalize_rows(bundle)" in text
    assert "rows = helper5210.normalize_rows(bundle)" not in text
    assert "5a3af6f274325813cbf3397baf25ce5a23ef63d95204642fe34534df83ba9feb" in text

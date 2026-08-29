import importlib.util
from pathlib import Path

P = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_m77_19_6_5_2_native_controlled_execution_parity_certification.py"
)

spec = importlib.util.spec_from_file_location("m", P)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def test_thresholds():
    assert m.SCORE_EPSILON == 1e-9
    assert m.CONFIDENCE_EPSILON == 1e-9
    assert m.DIRECTION_REQUIRED_PCT == 100.0
    assert m.SEMANTIC_HASH_REQUIRED_PCT == 100.0
    assert m.DETERMINISTIC_REPEAT_REQUIRED_PCT == 100.0


def test_comparison_count():
    assert m.REQUIRED_COMPARISONS_PER_CADENCE == 48


def test_semantic_hash_metadata_invariant():
    a = {"score": 1, "run_id": "a"}
    b = {"score": 1, "run_id": "b"}
    assert m.semantic_hash(a) == m.semantic_hash(b)


def test_semantic_hash_score_sensitive():
    assert m.semantic_hash({"score": 1}) != m.semantic_hash({"score": 2})


def test_empty_summary_fails():
    assert m.summarize([])["pass"] is False


def test_normalize_rows():
    bundle = {
        "price_history": [
            {
                "date": "2022-01-03",
                "open": 1,
                "high": 2,
                "low": 0.5,
                "close": 1.5,
                "volume": 100,
            }
        ]
    }
    rows = m.normalize_bundle_rows(bundle)
    assert rows[0]["date"].isoformat() == "2022-01-03"
    assert rows[0]["close"] == 1.5

import importlib.util
from pathlib import Path

P = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_m77_19_6_5_controlled_adapter_execution_parity_certification.py"
)

spec = importlib.util.spec_from_file_location("m77_19_6_5", P)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def test_strict_score_threshold():
    assert m.SCORE_EPSILON == 1e-9


def test_strict_confidence_threshold():
    assert m.CONFIDENCE_EPSILON == 1e-9


def test_direction_gate():
    assert m.DIRECTION_MATCH_REQUIRED_PCT == 100.0


def test_hash_gate():
    assert m.SEMANTIC_HASH_MATCH_REQUIRED_PCT == 100.0


def test_repeat_gate():
    assert m.DETERMINISTIC_REPEAT_REQUIRED_PCT == 100.0


def test_semantic_hash_ignores_run_metadata():
    a = {"symbol": "A", "score": 1, "run_id": "x"}
    b = {"symbol": "A", "score": 1, "run_id": "y"}
    assert m.semantic_hash(a) == m.semantic_hash(b)


def test_semantic_hash_keeps_score():
    assert m.semantic_hash({"score": 1}) != m.semantic_hash({"score": 2})


def test_empty_summary_fails():
    assert m.summarize([])["pass"] is False


def test_choose_adapter_ambiguous_fails_closed():
    c = [
        {"path": "a.py", "function": "replay", "args": [], "score": 10},
        {"path": "b.py", "function": "replay", "args": [], "score": 10},
    ]
    selected, ambiguity = m.choose_adapter(c, "DAILY")
    assert selected is None
    assert len(ambiguity) == 2


def test_verify_bundle_requires_price():
    bundle = {
        "cadence": "DAILY",
        "prediction_identity": {},
        "frozen_output": {},
        "frozen_profile": {},
        "frozen_lineage": {},
        "frozen_run_context": {},
        "price_history": [],
        "price_history_sha256": "x",
        "bundle_semantic_sha256": "y",
    }
    assert "EMPTY_PRICE_HISTORY" in m.verify_bundle(bundle)

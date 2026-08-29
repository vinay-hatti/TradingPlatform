import importlib.util
from pathlib import Path

RUNNER = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_m77_19_6_3_controlled_exact_input_parity_replay.py"
)

spec = importlib.util.spec_from_file_location("m77_19_6_3", RUNNER)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def test_strict_score_threshold():
    assert m.SCORE_EPSILON == 1e-9


def test_strict_confidence_threshold():
    assert m.CONFIDENCE_EPSILON == 1e-9


def test_direction_requires_100pct():
    assert m.DIRECTION_REQUIRED_PCT == 100.0


def test_semantic_hash_requires_100pct():
    assert m.SEMANTIC_HASH_REQUIRED_PCT == 100.0


def test_repeat_requires_100pct():
    assert m.DETERMINISTIC_REPEAT_REQUIRED_PCT == 100.0


def test_semantic_hash_deterministic():
    assert m.semantic_hash({"symbol": "AAPL", "score": 1}) == m.semantic_hash(
        {"symbol": "AAPL", "score": 1}
    )


def test_semantic_hash_ignores_run_id():
    assert m.semantic_hash(
        {"symbol": "AAPL", "score": 1, "run_id": "A"}
    ) == m.semantic_hash(
        {"symbol": "AAPL", "score": 1, "run_id": "B"}
    )


def test_semantic_hash_keeps_semantic_score():
    assert m.semantic_hash(
        {"symbol": "AAPL", "score": 1}
    ) != m.semantic_hash(
        {"symbol": "AAPL", "score": 2}
    )


def test_no_evidence_fails_closed():
    result = m.evaluate_actual_comparisons([])
    assert result["strict_parity_certified"] is False
    for cadence in m.CADENCES:
        assert result["cadences"][cadence]["pass"] is False


def test_normalize_cadence():
    assert m.normalize_cadence("1d") == "DAILY"
    assert m.normalize_cadence("1w") == "WEEKLY"
    assert m.normalize_cadence("1mo") == "MONTHLY"

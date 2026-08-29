from __future__ import annotations
import importlib.util
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[2] / "scripts" / "run_m77_19_6_2_exact_input_context_hash_parity.py"
spec = importlib.util.spec_from_file_location("m77_19_6_2", RUNNER)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)

def test_strict_thresholds_not_relaxed():
    assert m.STRICT_SCORE_EPSILON == 1e-9
    assert m.STRICT_CONFIDENCE_EPSILON == 1e-9
    assert m.STRICT_DIRECTION_MATCH_PCT == 100.0
    assert m.STRICT_SEMANTIC_HASH_MATCH_PCT == 100.0

def test_semantic_hash_is_deterministic():
    x = {"symbol":"AAPL","direction":"BULLISH","score":81.2,"generated_at":"2026-01-01T00:00:00Z"}
    assert m.semantic_hash(x) == m.semantic_hash(x)

def test_semantic_hash_ignores_generated_at():
    a = {"symbol":"AAPL","score":81.2,"generated_at":"A"}
    b = {"symbol":"AAPL","score":81.2,"generated_at":"B"}
    assert m.semantic_hash(a) == m.semantic_hash(b)

def test_semantic_hash_ignores_run_id():
    a = {"symbol":"AAPL","score":81.2,"run_id":"one"}
    b = {"symbol":"AAPL","score":81.2,"run_id":"two"}
    assert m.semantic_hash(a) == m.semantic_hash(b)

def test_semantic_hash_keeps_score():
    a = {"symbol":"AAPL","score":81.2}
    b = {"symbol":"AAPL","score":81.3}
    assert m.semantic_hash(a) != m.semantic_hash(b)

def test_semantic_hash_keeps_direction():
    a = {"symbol":"AAPL","direction":"BULLISH"}
    b = {"symbol":"AAPL","direction":"BEARISH"}
    assert m.semantic_hash(a) != m.semantic_hash(b)

def test_nested_metadata_is_removed():
    a = {"state":{"symbol":"AAPL","score":10,"snapshot_timestamp":"x"}}
    b = {"state":{"symbol":"AAPL","score":10,"snapshot_timestamp":"y"}}
    assert m.semantic_hash(a) == m.semantic_hash(b)

def test_diff_identifies_metadata_only():
    a = {"symbol":"AAPL","score":10,"run_id":"x"}
    b = {"symbol":"AAPL","score":10,"run_id":"y"}
    d = m.diff_flat(a,b)
    assert d["metadata_only"] is True
    assert d["different_field_count"] == 1

def test_diff_identifies_semantic_change():
    a = {"symbol":"AAPL","score":10}
    b = {"symbol":"AAPL","score":11}
    d = m.diff_flat(a,b)
    assert d["metadata_only"] is False

def test_infer_exact_authority_fail_closed():
    db = {"candidate_schemas":[]}
    x = m.infer_exact_input_authority(db)
    assert x["exact_input_replay_ready"] is False
    assert x["context_recovery_ready"] is False

def test_classify_fail_closed_without_db():
    report = {
        "database":{"available":False},
        "exact_input_authority":{"exact_input_replay_ready":False,"context_recovery_ready":False},
        "hash_semantics":{"source_hash_call_count":0,"semantic_markers_count":0},
        "external_context":{"source_context_marker_count":0},
    }
    status, blockers, controlled = m.classify(report)
    assert controlled is False
    assert status.startswith("BLOCKED")
    assert blockers

def test_projection_retains_semantic_identifiers():
    x = {"symbol":"AAPL","direction":"BULLISH","snapshot_id":"foo"}
    p = m.semantic_projection(x)
    assert p["symbol"] == "AAPL"
    assert p["direction"] == "BULLISH"
    assert "snapshot_id" not in p

import importlib.util
from pathlib import Path

P = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_m77_19_6_4_2_joined_frozen_replay_authority_recovery.py"
)

spec = importlib.util.spec_from_file_location("m77_19_6_4_2", P)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def test_cadences():
    assert m.CADENCES == ("DAILY", "WEEKLY", "MONTHLY")


def test_default_sample():
    assert m.DEFAULT_SAMPLE_PER_CADENCE == 48


def test_normalize_daily():
    assert m.normalize_cadence("1d") == "DAILY"


def test_normalize_weekly():
    assert m.normalize_cadence("1w") == "WEEKLY"


def test_normalize_monthly():
    assert m.normalize_cadence("1mo") == "MONTHLY"


def test_json_hash_deterministic():
    assert m.sha256_json({"a": 1}) == m.sha256_json({"a": 1})


def test_json_hash_changes():
    assert m.sha256_json({"a": 1}) != m.sha256_json({"a": 2})


def test_parse_jsonish_dict():
    assert m.parse_jsonish('{"a":1}') == {"a": 1}


def test_parse_jsonish_raw():
    assert m.parse_jsonish("not-json") == "not-json"


def test_jsonable_date():
    import datetime as dt
    assert m.jsonable(dt.date(2025, 1, 2)) == "2025-01-02"

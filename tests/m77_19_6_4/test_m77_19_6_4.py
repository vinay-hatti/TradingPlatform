import importlib.util
from pathlib import Path

RUNNER = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_m77_19_6_4_exact_frozen_input_context_replay_adapter.py"
)

spec = importlib.util.spec_from_file_location("m77_19_6_4", RUNNER)
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)


def test_cadences():
    assert m.CADENCES == ("DAILY", "WEEKLY", "MONTHLY")


def test_default_sample():
    assert m.DEFAULT_SAMPLE_PER_CADENCE == 48


def test_sha_deterministic():
    assert m.sha256_json({"a": 1}) == m.sha256_json({"a": 1})


def test_sha_semantic_change():
    assert m.sha256_json({"a": 1}) != m.sha256_json({"a": 2})


def test_detect_column():
    cols = ["symbol", "replay_date", "overall_score"]
    assert m.detect_column(cols, ("symbol", "ticker")) == "symbol"
    assert m.detect_column(cols, ("date", "replay_date")) == "replay_date"


def test_split_table():
    assert m.split_table("public.price_history") == ("public", "price_history")
    assert m.split_table("price_history") == ("public", "price_history")


def test_quote_ident():
    assert m.quote_ident("price_history") == '"price_history"'


def test_choose_replay_tables_by_name():
    profiles = [
        {"table": "public.m77_9_daily_replay", "cadence_column": None},
        {"table": "public.m77_2_weekly_replay", "cadence_column": None},
        {"table": "public.m77_10_monthly_replay", "cadence_column": None},
    ]
    selected = m.choose_replay_tables(profiles)
    assert selected["DAILY"] == "public.m77_9_daily_replay"
    assert selected["WEEKLY"] == "public.m77_2_weekly_replay"
    assert selected["MONTHLY"] == "public.m77_10_monthly_replay"


def test_choose_unified_fallback():
    profiles = [
        {"table": "public.stock_intelligence_replay", "cadence_column": "cadence"},
    ]
    selected = m.choose_replay_tables(profiles)
    assert all(v == "public.stock_intelligence_replay" for v in selected.values())

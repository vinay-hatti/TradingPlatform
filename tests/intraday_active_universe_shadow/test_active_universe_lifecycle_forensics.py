from __future__ import annotations
import importlib.util
from datetime import date
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "report_intraday_active_universe_lifecycle_forensics.py"
spec = importlib.util.spec_from_file_location("lifecycle_forensics", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def snap(day, ts, reasons):
    syms = sorted(reasons)
    return {
        "mode": "SHADOW_INTRADAY_DECISION",
        "market_session": True,
        "market_date": day,
        "generated_at": ts,
        "proposed_active_symbols": syms,
        "inclusion_reasons": {k: v for k, v in reasons.items()},
    }


def test_current_policy_qualification_not_hysteresis_only():
    reasons = {"STOCK_INTELLIGENCE_HIGH_SCORE", "ELIGIBILITY_HYSTERESIS"}
    assert mod.independently_qualified(reasons)
    assert mod.classify_membership(reasons) == "CURRENT_POLICY_QUALIFIED"


def test_hysteresis_only_classification():
    reasons = {"ELIGIBILITY_HYSTERESIS"}
    assert not mod.independently_qualified(reasons)
    assert mod.classify_membership(reasons) == "HYSTERESIS_ONLY"


def test_two_observation_hysteresis_is_bounded_pass():
    rows = [
        snap("2026-08-24", "2026-08-24T14:00:00+00:00", {"AAA": ["STOCK_INTELLIGENCE_HIGH_SCORE"]}),
        snap("2026-08-24", "2026-08-24T15:00:00+00:00", {"AAA": ["ELIGIBILITY_HYSTERESIS"]}),
        snap("2026-08-24", "2026-08-24T16:00:00+00:00", {"AAA": ["ELIGIBILITY_HYSTERESIS"]}),
        snap("2026-08-24", "2026-08-24T17:00:00+00:00", {}),
    ]
    r = mod.analyze_snapshots(rows, date(2026,8,24), date(2026,8,24))
    assert r["forensic_gate"] == "PASS"
    assert r["sticky_symbol_count"] == 0


def test_self_reinforcing_hysteresis_fails_after_two_observations():
    rows = [
        snap("2026-08-24", "2026-08-24T14:00:00+00:00", {"AAA": ["STOCK_INTELLIGENCE_HIGH_SCORE"]}),
        snap("2026-08-24", "2026-08-24T15:00:00+00:00", {"AAA": ["ELIGIBILITY_HYSTERESIS"]}),
        snap("2026-08-24", "2026-08-24T16:00:00+00:00", {"AAA": ["ELIGIBILITY_HYSTERESIS"]}),
        snap("2026-08-24", "2026-08-24T17:00:00+00:00", {"AAA": ["ELIGIBILITY_HYSTERESIS"]}),
    ]
    r = mod.analyze_snapshots(rows, date(2026,8,24), date(2026,8,24))
    assert r["forensic_gate"] == "FAIL"
    assert r["sticky_symbol_count"] == 1
    assert r["sticky_symbols"][0]["symbol"] == "AAA"


def test_cross_session_carry_without_current_qualification_is_counted():
    rows = [
        snap("2026-08-24", "2026-08-24T20:00:00+00:00", {"AAA": ["STOCK_INTELLIGENCE_HIGH_SCORE"]}),
        snap("2026-08-25", "2026-08-25T14:00:00+00:00", {"AAA": ["ELIGIBILITY_HYSTERESIS"]}),
    ]
    r = mod.analyze_snapshots(rows, date(2026,8,24), date(2026,8,25))
    assert r["forensic_gate"] == "FAIL"
    assert r["cross_session_carried_without_current_qualification_total"] == 1
    assert r["daily"][1]["carried_without_current_qualification_symbols"] == ["AAA"]


def test_safety_and_mandatory_are_independent_qualifiers():
    assert mod.independently_qualified({"OPEN_POSITION", "ELIGIBILITY_HYSTERESIS"})
    assert mod.independently_qualified({"MANDATORY_CORE_ETF_REFERENCE"})


def test_monotonic_growth_detected():
    rows = [
        snap("2026-08-24", "2026-08-24T14:00:00+00:00", {"AAA": ["STOCK_INTELLIGENCE_HIGH_SCORE"]}),
        snap("2026-08-24", "2026-08-24T15:00:00+00:00", {"AAA": ["ELIGIBILITY_HYSTERESIS"], "BBB": ["STOCK_INTELLIGENCE_HIGH_SCORE"]}),
    ]
    r = mod.analyze_snapshots(rows, date(2026,8,24), date(2026,8,24))
    assert r["active_count_monotonic_non_decreasing"] is True

from datetime import date
import importlib.util
from pathlib import Path

import pytest

from trading_ai.opex_intelligence.governance import (
    binary_brier_score,
    binary_log_loss,
    expected_calibration_error,
    is_monthly_opex,
    monthly_opex_date,
    settlement_convention,
    state_hash,
    trading_dte,
    trading_sessions,
)
from trading_ai.opex_intelligence.service import OpexIntelligenceService


ROOT = Path(__file__).resolve().parents[2]


def test_monthly_opex_is_holiday_aware():
    # The third Friday was Good Friday, so the governed monthly cycle moved to Thursday.
    assert monthly_opex_date(2025, 4) == date(2025, 4, 17)
    assert is_monthly_opex(date(2025, 4, 17))
    assert not is_monthly_opex(date(2025, 4, 18))


def test_full_trading_path_reaches_second_and_third_cycle_expirations():
    start = date(2026, 8, 15)
    september = trading_sessions(start, date(2026, 9, 18), include_start=True)
    october = trading_sessions(start, date(2026, 10, 16), include_start=True)
    assert september[-1] == date(2026, 9, 18)
    assert october[-1] == date(2026, 10, 16)
    assert len(september) == trading_dte(start, date(2026, 9, 18))
    assert len(october) == trading_dte(start, date(2026, 10, 16))
    assert len(october) > 22


def test_standard_monthly_settlement_is_special_opening_truth():
    assert settlement_convention("SPX", date(2026, 9, 18))["settlement_symbol"] == "SET"
    assert settlement_convention("NDX", date(2026, 9, 18))["settlement_symbol"] == "XQO"
    assert settlement_convention("RUT", date(2026, 9, 18))["settlement_symbol"] == "RLS"
    assert all(
        settlement_convention(symbol, date(2026, 9, 18))["settlement_style"]
        == "AM_OPENING_SPECIAL_QUOTATION"
        for symbol in ("SPX", "NDX", "RUT")
    )


def test_semantic_fingerprint_is_order_stable_and_value_sensitive():
    left = {"symbol": "SPX", "inputs": {"spot": 6400, "dte": 34}}
    same = {"inputs": {"dte": 34, "spot": 6400}, "symbol": "SPX"}
    changed = {"symbol": "SPX", "inputs": {"spot": 6401, "dte": 34}}
    assert state_hash(left) == state_hash(same)
    assert state_hash(left) != state_hash(changed)


def test_binary_proper_scoring_metrics_are_bounded_and_deterministic():
    rows = [(0.8, 1), (0.2, 0), (0.6, 1), (0.4, 0)]
    assert round(binary_brier_score(rows), 6) == 0.1
    assert binary_log_loss(rows) > 0
    assert 0 <= expected_calibration_error(rows) <= 1


def test_expected_path_is_scenario_weighted_not_dominant_only():
    service = OpexIntelligenceService(lambda: None)
    scenarios = [
        {"name": "BULLISH_BREAKOUT", "probability": 40, "target": 110},
        {"name": "BEARISH_BREAKDOWN", "probability": 35, "target": 90},
        {"name": "PIN_RANGE", "probability": 25, "target": 100},
    ]
    rows = service._expected_daily_path(
        date(2026, 8, 10),
        date(2026, 8, 14),
        100,
        scenarios,
        [{"stage": 1, "low": 99, "high": 101}],
        [],
        [],
        {"score": 50},
        {"rv20": 16},
    )
    assert rows[-1]["path_method"] == "SCENARIO_WEIGHTED_EXPECTATION"
    assert 99 < rows[-1]["median"] < 102


def test_backend_has_exact_authority_and_noop_guards():
    source = (ROOT / "src/trading_ai/opex_intelligence/service.py").read_text()
    for token in (
        "pg_try_advisory_xact_lock",
        "NOOP_UNCHANGED_AUTHORITY",
        "forecast_ids",
        "authority_input_fingerprint",
        "EXACT_COVERAGE_GATE_FAILED",
        "DEFERRED_INCOMPLETE_INPUT",
        "OptionValuationEventModel.symbol.in_",
        "POLYGON_SPECIAL_INDEX",
        "OFFICIAL_SPECIAL_OPENING_QUOTATION_ONLY",
    ):
        assert token in source


def test_ui_exposes_shadow_governance_and_lineage():
    source = (ROOT / "ui/workstation/src/OpexIntelligencePage.tsx").read_text()
    for token in (
        "Governance and current authority",
        "DISABLED — EVIDENCE ONLY",
        "Authority fingerprint",
        "Input fingerprint",
        "ABSTAIN",
        "Independent-cycle forecast calibration",
        "Scenario-weighted day-by-day path through OPEX",
        "UNCALIBRATED",
    ):
        assert token in source


def test_migration_and_cleanup_contracts_are_present():
    migration = (ROOT / "migrations/versions/m71_004_governed_opex_authority.py").read_text()
    cleanup = (ROOT / "scripts/run_m71_4_opex_cleanup.py").read_text()
    for token in (
        "input_fingerprint",
        "authority_input_fingerprint",
        "opex_settlement_values",
        "sample_group_key",
    ):
        assert token in migration
    for token in (
        "PURGE_NONAUTHORITATIVE_OPEX_DUPLICATES",
        "current_authority_ids",
        "authority_preservation",
        "settlement_source.is_(None)",
    ):
        assert token in cleanup


def test_downstream_governance_patch_is_contextual_and_idempotent(tmp_path):
    patch_path = ROOT / "scripts/apply_m71_4_downstream_governance.py"
    spec = importlib.util.spec_from_file_location("m714_downstream_patch", patch_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    target = tmp_path / "service.py"
    target.write_text(
        "class Service:\n"
        "    VERSION='NEWER-M74'\n"
        "    def _intelligence(self,p,market):\n"
        "        meta={}\n"
        "        opex=_f(meta.get('opex_score'),50) or 50\n"
        "        ret=0\n"
        "    def untouched(self):\n"
        "        return 'preserved'\n"
    )
    assert module.patch_service(target) == "PATCHED_SHADOW_FAIL_CLOSED"
    patched = target.read_text()
    assert "VERSION='NEWER-M74'" in patched
    assert "return 'preserved'" in patched
    assert "opex_governance_status" in patched
    assert "HUMAN_APPROVED" in patched
    assert module.patch_service(target) == "NOOP_ALREADY_GOVERNED"


def test_downstream_governance_patch_accepts_absent_opex_coupling(tmp_path):
    patch_path = ROOT / "scripts/apply_m71_4_downstream_governance.py"
    spec = importlib.util.spec_from_file_location("m714_no_coupling_patch", patch_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    target = tmp_path / "service.py"
    original = (
        "class Service:\n"
        "    VERSION='NEWER-M74'\n"
        "    def _intelligence(self,p,market):\n"
        "        score=50\n"
        "        return score\n"
        "    def untouched(self):\n"
        "        return 'preserved'\n"
    )
    target.write_text(original)
    assert module.patch_service(target) == "NOOP_NO_OPEX_COUPLING"
    assert target.read_text() == original


def test_downstream_governance_patch_rejects_ambiguous_opex_usage(tmp_path):
    patch_path = ROOT / "scripts/apply_m71_4_downstream_governance.py"
    spec = importlib.util.spec_from_file_location("m714_ambiguous_patch", patch_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    target = tmp_path / "service.py"
    target.write_text(
        "class Service:\n"
        "    def _intelligence(self,p,market):\n"
        "        score=meta.get('opex_score')\n"
        "        return score\n"
        "    def untouched(self):\n"
        "        return 'preserved'\n"
    )
    with pytest.raises(RuntimeError, match="recognized OPEX score assignment"):
        module.patch_service(target)


def test_downstream_governance_patch_matches_production_inline_assignment(tmp_path):
    patch_path = ROOT / "scripts/apply_m71_4_downstream_governance.py"
    spec = importlib.util.spec_from_file_location("m7142_production_patch", patch_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    target = tmp_path / "service.py"
    target.write_text(
        "class Service:\n"
        "    def _intelligence(self,p,market):\n"
        "        meta=dict(p.metadata_json or {});health=dict(p.health_json or {})\n"
        "        trend=_f(meta.get('trend_score'),50) or 50;dealer=_f(meta.get('dealer_score'),50) or 50;portfolio=_f(meta.get('portfolio_fit_score'),50) or 50;opex=_f(meta.get('opex_score'),50) or 50\n"
        "        components={'TREND':trend,'OPEX':opex}\n"
        "        return components\n"
        "    def untouched(self):\n"
        "        return 'preserved'\n"
    )
    assert module.patch_service(target) == "PATCHED_SHADOW_FAIL_CLOSED"
    patched = target.read_text()
    assert "portfolio=_f(meta.get('portfolio_fit_score'),50) or 50\n" in patched
    assert "opex_status=str(meta.get('opex_governance_status') or 'ABSTAIN').upper()" in patched
    assert "if opex_status=='HUMAN_APPROVED' else 50" in patched
    assert "components={'TREND':trend,'OPEX':opex}" in patched
    compile(patched, str(target), "exec")

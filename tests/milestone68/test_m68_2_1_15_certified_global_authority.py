from __future__ import annotations

from pathlib import Path

from trading_ai.institutional_options.trade_builder_authority import (
    classify_trade_builder_authority,
)
from trading_ai.trade_plan_certification.engine import (
    certify_institutional_underlying_plan,
)


ROOT = Path(__file__).resolve().parents[2]


def final_certification(**overrides) -> dict:
    value = {
        "certification_id": "TPC-IO-TEST",
        "status": "PASS",
        "certification_scope": "INSTITUTIONAL_OPTIONS_FINAL_PLAN",
        "execution_disposition": "READY_NOW",
        "trade_builder_ready": True,
        "plan_fingerprint": "plan-test",
    }
    value.update(overrides)
    return value


def test_missing_certification_can_never_authorize_true_ready_flag() -> None:
    authority = classify_trade_builder_authority({}, True)
    assert authority["authorized"] is False
    assert authority["column_consistent"] is False
    assert "FINAL_CERTIFICATION_MISSING" in authority["reason_codes"]
    assert "READY_FLAG_WITHOUT_VALID_CERTIFICATION" in authority["reason_codes"]


def test_valid_final_certification_and_ready_flag_are_authoritative() -> None:
    authority = classify_trade_builder_authority(
        {"trade_plan_certification": final_certification()},
        True,
    )
    assert authority["authorized"] is True
    assert authority["column_consistent"] is True
    assert authority["reason_codes"] == []


def test_waiting_entry_is_structurally_valid_but_not_executable_now() -> None:
    authority = classify_trade_builder_authority(
        {"trade_plan_certification": final_certification(
            execution_disposition="WAITING_FOR_ENTRY",
            trade_builder_ready=False,
            entry_execution={
                "reason_codes": ["REFERENCE_PRICE_ABOVE_ENTRY_ZONE"]
            },
        )},
        False,
    )
    assert authority["authorized"] is False
    assert authority["column_consistent"] is True
    assert "EXECUTION_DISPOSITION_NOT_READY_NOW" in authority["reason_codes"]
    assert "REFERENCE_PRICE_ABOVE_ENTRY_ZONE" in authority["reason_codes"]
    assert authority["blocking_reason_codes"] == [
        "EXECUTION_DISPOSITION_NOT_READY_NOW",
        "CERTIFICATION_TRADE_BUILDER_READY_FALSE",
    ]
    assert authority["entry_reason_codes"] == [
        "REFERENCE_PRICE_ABOVE_ENTRY_ZONE"
    ]


def certification(reference_price: float) -> dict:
    return certify_institutional_underlying_plan(
        stock_certification={
            "certification_id": "TPC-STOCK-TEST",
            "status": "PASS",
            "plan_fingerprint": "stock-plan",
            "reference_market": {
                "price": reference_price,
                "timestamp": "2026-08-16T20:00:00Z",
                "provider": "POLYGON",
            },
        },
        direction="BULLISH",
        entry_zone_low=55.7467,
        entry_zone_high=56.1181,
        structural_stop=54.6837,
        targets=[61.9733, 64.0],
        strategy="BULL_CALL_SPREAD",
        legs=[
            {
                "side": "BUY",
                "option_symbol": "O:XLE260918C00056000",
                "expiry": "2026-09-18",
                "strike": 56,
            },
            {
                "side": "SELL",
                "option_symbol": "O:XLE260918C00062000",
                "expiry": "2026-09-18",
                "strike": 62,
            },
        ],
        contract_executable=True,
        dynamic_management={
            "underlying_stop": 54.6837,
            "underlying_targets": [61.9733, 64.0],
            "trailing_policy": "UNDERLYING_HIGHER_LOW",
            "volatility_exit_rule": "IV_COLLAPSE",
        },
        entry_policy={
            "entry_type": "DEMAND_BOUNCE",
            "preferred_entry": 55.9324,
            "zone_low": 55.7467,
            "zone_high": 56.1181,
            "confirmation_trigger": 62.1181,
            "chase_limit": 56.6038,
        },
        geometry_context={"atr": 1.48},
    )


def test_conditional_entry_interface_handles_ready_and_extended_market() -> None:
    ready = certification(55.90)
    extended = certification(61.91)
    assert ready["status"] == "PASS"
    assert ready["trade_builder_ready"] is True
    assert ready["execution_disposition"] == "READY_NOW"
    assert extended["status"] == "PASS"
    assert extended["trade_builder_ready"] is False
    assert extended["execution_disposition"] == "REGENERATE_REQUIRED"
    assert "TARGET_1_REMAINING_ROOM_INSUFFICIENT" in (
        extended["entry_execution"]["reason_codes"]
    )


def test_positive_ready_now_entry_evidence_never_blocks_authority() -> None:
    certified = certification(55.90)
    assert certified["entry_execution"]["reason_codes"] == [
        "REFERENCE_PRICE_WITHIN_GOVERNED_ENTRY_RANGE"
    ]

    authority = classify_trade_builder_authority(
        {"trade_plan_certification": certified},
        True,
    )

    assert authority["authorized"] is True
    assert authority["certification_valid"] is True
    assert authority["column_consistent"] is True
    assert authority["blocking_reason_codes"] == []
    assert authority["entry_reason_codes"] == [
        "REFERENCE_PRICE_WITHIN_GOVERNED_ENTRY_RANGE"
    ]
    assert "READY_FLAG_WITHOUT_VALID_CERTIFICATION" not in (
        authority["reason_codes"]
    )


def test_source_contracts_cover_all_authority_boundaries() -> None:
    decision = (
        ROOT / "src/trading_ai/institutional_options/decision.py"
    ).read_text(encoding="utf-8")
    repository = (
        ROOT / "src/trading_ai/institutional_options/repository.py"
    ).read_text(encoding="utf-8")
    advancement = (
        ROOT / "src/trading_ai/institutional_options/advancement_authority.py"
    ).read_text(encoding="utf-8")
    portfolio = (
        ROOT / "src/trading_ai/portfolio_risk_allocation/optimizer.py"
    ).read_text(encoding="utf-8")
    migration = (
        ROOT / "migrations/versions/m68_004_certified_trade_builder_authority.py"
    ).read_text(encoding="utf-8")
    assert "classify_trade_builder_authority" in decision
    assert 'ready_for_trade_builder=authority["authorized"]' in repository
    assert "INVALID_TRADE_BUILDER_READINESS" in advancement
    assert "certified_ready_opportunity_ids" in portfolio
    assert "terminal_stage_counts" in portfolio
    assert "NOT VALID" in migration
    assert "IS TRUE" in migration
    recovery = (
        ROOT / "scripts/run_m68_2_1_15_rebuild_certified_global_authority.py"
    ).read_text(encoding="utf-8")
    assert "latest_published_stock_scanner_run_id" in recovery

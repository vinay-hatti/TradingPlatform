from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from trading_ai.portfolio_risk_allocation.service import (
    PortfolioRiskAllocationService,
)


def _snapshot(updated_at: str) -> dict:
    return {
        "snapshot_id": "M64-RISK-TEST",
        "portfolio_id": "PAPER-PRIMARY",
        "snapshot_timestamp": "2026-08-15T20:00:00+00:00",
        "status": "READY",
        "health_score": 95.0,
        "net_liquidation": 100_000.0,
        "buying_power": 200_000.0,
        "capital_committed": 500.0,
        "open_risk": 500.0,
        "var_95": 250.0,
        "expected_shortfall_95": 350.0,
        "portfolio_heat_pct": 0.5,
        "concentration_score": 10.0,
        "diversification_score": 90.0,
        "payload_json": {
            "generated_by": "m64-dedicated-scheduled-owner",
            "capital": {
                "net_liquidation": 100_000.0,
                "buying_power": 200_000.0,
                "trading_risk_basis": (
                    "GOVERNED_PRE_EXPIRATION_DEFINED_LOSS"
                ),
            },
            "positions": [{
                "symbol": "AAPL",
                "managed_position_id": "position-1",
                "expiration_guard_armed": True,
                "expiration_guard": {
                    "instruction_id": "exit-instruction-1",
                    "status": "ACTIVE",
                    "policy": (
                        "FULL_POSITION_EXIT_AT_LEAST_1_TRADING_DAY_"
                        "BEFORE_EARLIEST_LEG_EXPIRY"
                    ),
                    "exit_on_or_before_date": "2026-09-10",
                    "updated_at": updated_at,
                },
            }],
        },
    }


def test_guard_refresh_timestamp_does_not_change_risk_semantics():
    before = _snapshot("2026-08-15T20:05:00+00:00")
    after = _snapshot("2026-08-15T20:10:00+00:00")

    assert (
        PortfolioRiskAllocationService.semantic_fingerprint(before)
        == PortfolioRiskAllocationService.semantic_fingerprint(after)
    )


def test_substantive_expiration_guard_changes_remain_governed():
    baseline = _snapshot("2026-08-15T20:05:00+00:00")
    changed_exit_date = deepcopy(baseline)
    changed_exit_date["payload_json"]["positions"][0][
        "expiration_guard"
    ]["exit_on_or_before_date"] = "2026-09-09"
    changed_status = deepcopy(baseline)
    changed_status["payload_json"]["positions"][0][
        "expiration_guard"
    ]["status"] = "CANCELLED"
    disarmed = deepcopy(baseline)
    disarmed["payload_json"]["positions"][0][
        "expiration_guard_armed"
    ] = False

    baseline_fingerprint = (
        PortfolioRiskAllocationService.semantic_fingerprint(baseline)
    )
    for changed in (changed_exit_date, changed_status, disarmed):
        assert (
            PortfolioRiskAllocationService.semantic_fingerprint(changed)
            != baseline_fingerprint
        )


def test_release_source_removes_only_nested_guard_updated_at():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "src/trading_ai/portfolio_risk_allocation/service.py"
    ).read_text()

    assert "EXPIRATION_GUARD_SEMANTIC_FIELDS" in source
    assert '"exit_on_or_before_date"' in source
    assert '"updated_at"' not in source.split(
        "EXPIRATION_GUARD_SEMANTIC_FIELDS", 1
    )[1].split(")", 1)[0]
    assert 'payload.pop("updated_at", None)' not in source
    assert any(version in source for version in (
        "M64.2.4.5-RISK-SEMANTIC-FINGERPRINT-1.0",
        "M64.2.4.7-BASELINE-MATERIAL-RISK-AUTHORITY-1.0",
    ))

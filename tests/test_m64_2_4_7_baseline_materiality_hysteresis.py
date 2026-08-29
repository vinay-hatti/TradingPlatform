from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from trading_ai.portfolio_risk_allocation.service import (
    PortfolioRiskAllocationService,
)


def _snapshot(option_mark: float = 10.024) -> dict:
    return {
        "snapshot_id": "M64-RISK-BASELINE",
        "portfolio_id": "PAPER-PRIMARY",
        "snapshot_timestamp": "2026-08-15T20:53:45+00:00",
        "broker_publication_id": "M63-PUB-CURRENT",
        "status": "READY",
        "health_score": 95.0,
        "net_liquidation": 3_900_000.0,
        "buying_power": 3_800_000.0,
        "capital_committed": 500.0,
        "open_risk": 500.0,
        "var_95": 12_491.978,
        "expected_shortfall_95": 15_596.046,
        "portfolio_heat_pct": 0.0128,
        "concentration_score": 100.0,
        "diversification_score": 0.0,
        "payload_json": {
            "position_count": 1,
            "positions": [{
                "symbol": "AAPL",
                "contract_id": "AAPL-20260918-200-C",
                "option_symbol": "O:AAPL260918C00200000",
                "managed_position_id": "position-aapl",
                "security_type": "OPT",
                "quantity": 1.0,
                "multiplier": 100.0,
                "expiry": "2026-09-18",
                "strike": 200.0,
                "right": "C",
                "strategy": "LONG_CALL",
                "sector": "INFORMATION TECHNOLOGY",
                "industry": "TECHNOLOGY",
                "theme": "TECHNOLOGY",
                "lineage": {"trade_plan_id": "plan-aapl"},
                "expiration_guard_armed": True,
                "expiration_guard": {
                    "label": "EXPIRATION_GUARD_EXIT",
                    "mandatory_exit": True,
                    "exit_on_or_before_date": "2026-09-17",
                    "updated_at": "2026-08-15T20:53:00+00:00",
                },
                "quote_quality": "EXACT_POLYGON",
                "classification_quality": "GOVERNED",
                "risk_method": "LONG_PREMIUM",
                "market_value": 1_000.0,
                "capital_committed": 500.0,
                "maximum_loss": 500.0,
                "managed_entry_value": 500.0,
                "option_mark": option_mark,
                "underlying_price": 225.0,
                "implied_volatility": 0.2138,
                "realized_volatility_20d": 0.25,
                "beta": 1.10,
                "greeks": {
                    "delta": 51.98,
                    "gamma": 12.46,
                    "theta": -2.10,
                    "vega": 6.03,
                    "rho": 1.0,
                },
            }],
            "structures": [],
            "greeks": {
                "delta": 51.98,
                "gamma": 12.46,
                "theta": -2.10,
                "vega": 6.03,
                "rho": 1.0,
                "beta_weighted_delta": 11_695.5,
            },
            "exposures": {
                "symbol": {"AAPL": 1_000.0},
                "sector": {"INFORMATION TECHNOLOGY": 1_000.0},
                "strategy": {"LONG_CALL": 1_000.0},
            },
            "capital": {
                "net_liquidation": 3_900_000.0,
                "buying_power": 3_800_000.0,
                "market_value": 1_000.0,
                "capital_committed": 500.0,
                "open_risk": 500.0,
                "gross_leg_open_risk": 500.0,
                "capital_usage_pct": 0.0128,
                "portfolio_heat_pct": 0.0128,
                "trading_risk_basis": (
                    "GOVERNED_PRE_EXPIRATION_DEFINED_LOSS"
                ),
                "operational_risk": {
                    "status": "LOW",
                    "expiration_guards_armed": 1,
                },
                "heat_risk_decomposition": {
                    "methodology": "GOVERNED_DEFINED_LOSS",
                    "governed_strategy_risk": 500.0,
                },
            },
            "risk": {
                "var_95_one_day": 12_491.978,
                "expected_shortfall_95_one_day": 15_596.046,
                "methodology": "DELTA_GAMMA_VEGA_1D_PROXY",
                "concentration_hhi": 1.0,
                "concentration_score": 100.0,
                "diversification_score": 0.0,
                "stress": {
                    "SPY_DOWN_5": {"estimated_pnl": -9_374.29},
                },
            },
            "data_quality": {
                "exact_option_quote_coverage_pct": 100.0,
                "governed_classification_coverage_pct": 100.0,
                "warnings": [],
                "structure_count": 0,
                "multi_leg_position_count": 0,
            },
            "limits": {
                "max_symbol_pct": 10,
                "max_sector_pct": 25,
                "max_strategy_pct": 35,
                "max_portfolio_heat_pct": 20,
                "risk_per_trade_pct": 2,
            },
        },
    }


def _seal(snapshot: dict) -> dict:
    payload = snapshot["payload_json"]
    payload["semantic_fingerprint"] = (
        PortfolioRiskAllocationService.semantic_fingerprint(snapshot)
    )
    payload["state_integrity_fingerprint"] = (
        PortfolioRiskAllocationService.state_integrity_fingerprint(snapshot)
    )
    return snapshot


def test_rounding_boundary_does_not_create_material_authority():
    baseline = _seal(_snapshot(10.024))
    candidate = _seal(_snapshot(10.026))
    candidate["snapshot_id"] = "M64-RISK-CANDIDATE"
    candidate["snapshot_timestamp"] = "2026-08-15T20:54:59+00:00"
    candidate = _seal(candidate)

    assert (
        PortfolioRiskAllocationService.semantic_fingerprint(baseline)
        != PortfolioRiskAllocationService.semantic_fingerprint(candidate)
    )
    evaluation = PortfolioRiskAllocationService.materiality_evaluation(
        baseline,
        candidate,
    )
    assert evaluation["status"] == "EQUIVALENT"
    assert evaluation["suppressed_submaterial_change_count"] >= 1

    resolution = PortfolioRiskAllocationService.resolve_material_authority(
        candidate,
        baseline,
    )
    assert resolution["status"] == "BASELINE_EQUIVALENT"
    assert resolution["reuse_published_semantics"] is True
    assert resolution["effective_semantic_fingerprint"] == (
        baseline["payload_json"]["semantic_fingerprint"]
    )


def test_material_numeric_change_crosses_sticky_baseline():
    baseline = _seal(_snapshot(10.024))
    candidate = _snapshot(10.08)
    candidate["snapshot_id"] = "M64-RISK-MATERIAL"
    candidate = _seal(candidate)

    evaluation = PortfolioRiskAllocationService.materiality_evaluation(
        baseline,
        candidate,
    )
    assert evaluation["status"] == "MATERIAL_CHANGE"
    assert evaluation["material_numeric_change_count"] >= 1
    resolution = PortfolioRiskAllocationService.resolve_material_authority(
        candidate,
        baseline,
    )
    assert resolution["status"] == "MATERIAL_CHANGE"
    assert resolution["reuse_published_semantics"] is False


def test_structural_position_change_crosses_sticky_baseline():
    baseline = _seal(_snapshot())
    candidate = deepcopy(_snapshot())
    candidate["snapshot_id"] = "M64-RISK-STRUCTURAL"
    candidate["payload_json"]["positions"][0]["quantity"] = 2.0
    candidate = _seal(candidate)

    evaluation = PortfolioRiskAllocationService.materiality_evaluation(
        baseline,
        candidate,
    )
    assert evaluation["status"] == "MATERIAL_CHANGE"
    assert evaluation["structural_change_count"] >= 1


def test_corrupt_baseline_is_never_reused():
    baseline = _seal(_snapshot())
    baseline["net_liquidation"] += 0.01
    candidate = _seal(_snapshot())

    resolution = PortfolioRiskAllocationService.resolve_material_authority(
        candidate,
        baseline,
    )
    assert resolution["status"] == "BASELINE_INTEGRITY_INVALID"
    assert resolution["baseline_integrity_valid"] is False
    assert resolution["reuse_published_semantics"] is False


def test_release_source_uses_baseline_relative_materiality():
    root = Path(__file__).resolve().parents[1]
    service = (
        root / "src/trading_ai/portfolio_risk_allocation/service.py"
    ).read_text()
    orchestration = (
        root / "src/trading_ai/portfolio_risk_allocation/orchestration.py"
    ).read_text()
    scheduled = (
        root / "scripts/run_m64_portfolio_intelligence.py"
    ).read_text()

    for token in (
        "M64.2.4.7-BASELINE-MATERIAL-RISK-AUTHORITY-1.0",
        "M64.2.4.7-BASELINE-RELATIVE-MATERIALITY-1.0",
        "def materiality_projection",
        "def materiality_evaluation",
        "def resolve_material_authority",
        "BASELINE_EQUIVALENT",
        "suppressed_submaterial_change_count",
    ):
        assert token in service
    assert "M64.2.4.7-AUTHORITY-INPUT-FINGERPRINT-1.0" in orchestration
    assert '"_risk_materiality": risk_materiality' in orchestration
    assert "M64.2.4.7-SCHEDULED-PROGRESS-1.0" in scheduled

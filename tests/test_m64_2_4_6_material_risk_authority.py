from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from trading_ai.portfolio_risk_allocation.service import (
    PortfolioRiskAllocationService,
)


def _snapshot() -> dict:
    positions = [
        {
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
            "strategy": "BULL_CALL_SPREAD",
            "sector": "INFORMATION TECHNOLOGY",
            "industry": "TECHNOLOGY",
            "theme": "TECHNOLOGY",
            "lineage": {"trade_plan_id": "plan-aapl"},
            "expiration_guard_armed": True,
            "expiration_guard": {
                "label": "EXPIRATION_GUARD_EXIT",
                "trigger_type": "EXPIRATION_GUARD_DATE",
                "exit_on_or_before_date": "2026-09-17",
                "mandatory_exit": True,
                "management_generation": 1,
                "armed_at": "2026-08-10T15:00:00+00:00",
                "updated_at": "2026-08-15T20:26:00+00:00",
            },
            "quote_quality": "EXACT_POLYGON",
            "classification_quality": "RECONSTRUCTED_MULTI_LEG",
            "risk_method": "LONG_PREMIUM",
            "structure_id": "AAPL:2026-09-18:C:200-205",
            "market_value": 1_000.0,
            "capital_committed": 500.0,
            "maximum_loss": 500.0,
            "managed_entry_value": 500.0,
            "structure_maximum_loss": 500.0,
            "structure_maximum_profit": 0.0,
            "option_mark": 10.0,
            "underlying_price": 225.0,
            "implied_volatility": 0.21382018576459172,
            "realized_volatility_20d": 0.25,
            "beta": 1.10,
            "greeks": {
                "delta": 51.983559346165386,
                "gamma": 12.459096493340187,
                "theta": -2.0950441932195822,
                "vega": 6.033466351347724,
                "rho": 1.0,
            },
        },
        {
            "symbol": "AAPL",
            "contract_id": "AAPL-20260918-205-C",
            "option_symbol": "O:AAPL260918C00205000",
            "managed_position_id": "position-aapl",
            "security_type": "OPT",
            "quantity": -1.0,
            "multiplier": 100.0,
            "expiry": "2026-09-18",
            "strike": 205.0,
            "right": "C",
            "strategy": "BULL_CALL_SPREAD",
            "sector": "INFORMATION TECHNOLOGY",
            "industry": "TECHNOLOGY",
            "theme": "TECHNOLOGY",
            "lineage": {"trade_plan_id": "plan-aapl"},
            "expiration_guard_armed": True,
            "expiration_guard": {
                "label": "EXPIRATION_GUARD_EXIT",
                "trigger_type": "EXPIRATION_GUARD_DATE",
                "exit_on_or_before_date": "2026-09-17",
                "mandatory_exit": True,
                "management_generation": 1,
                "armed_at": "2026-08-10T15:00:00+00:00",
                "updated_at": "2026-08-15T20:26:00+00:00",
            },
            "quote_quality": "EXACT_POLYGON",
            "classification_quality": "RECONSTRUCTED_MULTI_LEG",
            "risk_method": "SHORT_OPTION_CONSERVATIVE",
            "structure_id": "AAPL:2026-09-18:C:200-205",
            "market_value": 500.0,
            "capital_committed": 0.0,
            "maximum_loss": 500.0,
            "managed_entry_value": 500.0,
            "structure_maximum_loss": 500.0,
            "structure_maximum_profit": 0.0,
            "option_mark": 5.0,
            "underlying_price": 225.0,
            "implied_volatility": 0.29881953885531165,
            "realized_volatility_20d": 0.25,
            "beta": 1.10,
            "greeks": {
                "delta": -63.777796538031474,
                "gamma": -2.5282227826167163,
                "theta": 11.56561140733802,
                "vega": -19.424327825309156,
                "rho": -1.0,
            },
        },
    ]
    payload = {
        "policy_version": PortfolioRiskAllocationService.POLICY_VERSION,
        "generated_by": "m64-dedicated-scheduled-owner",
        "position_count": 2,
        "greeks": {
            "delta": 800.3750789063927,
            "gamma": 38.010578071065474,
            "theta": -52.34680479965216,
            "vega": 451.8139752584172,
            "rho": 0.0,
            "beta_weighted_delta": 310_993.2040662526,
        },
        "exposures": {
            "symbol": {"AAPL": 1_500.0},
            "sector": {"INFORMATION TECHNOLOGY": 1_500.0},
            "strategy": {"BULL_CALL_SPREAD": 1_500.0},
        },
        "capital": {
            "net_liquidation": 3_900_000.0,
            "buying_power": 3_800_000.0,
            "market_value": 1_500.0,
            "capital_committed": 500.0,
            "capital_usage_pct": 0.0128,
            "open_risk": 500.0,
            "gross_leg_open_risk": 1_000.0,
            "trading_risk_basis": (
                "GOVERNED_PRE_EXPIRATION_DEFINED_LOSS"
            ),
            "operational_risk": {
                "status": "LOW",
                "expiration_guards_armed": 1,
                "nearest_mandatory_exit_date": "2026-09-17",
            },
            "portfolio_heat_pct": 0.0128,
            "heat_risk_decomposition": {
                "methodology": (
                    "M64_2_GOVERNED_DEBIT_PREMIUM_THEN_DEFINED_MAX_LOSS"
                ),
                "governed_strategy_risk": 500.0,
            },
        },
        "risk": {
            "var_95_one_day": 12_491.978807607167,
            "expected_shortfall_95_one_day": 15_596.046268891372,
            "methodology": "DELTA_GAMMA_VEGA_1D_PROXY",
            "concentration_hhi": 1.0,
            "concentration_score": 100.0,
            "diversification_score": 0.0,
            "stress": {
                "CORRELATION_BREAKDOWN": {
                    "estimated_pnl": -9_268.832970517235,
                },
                "DEALER_UNWIND": {
                    "estimated_pnl": -11_077.518739203622,
                },
            },
        },
        "data_quality": {
            "exact_option_quote_coverage_pct": 100.0,
            "governed_classification_coverage_pct": 100.0,
            "warnings": [],
            "structure_count": 1,
            "multi_leg_position_count": 2,
        },
        "structures": [{
            "structure_id": "AAPL:2026-09-18:C:200-205",
            "symbol": "AAPL",
            "expiry": "2026-09-18",
            "strategy": "BULL_CALL_SPREAD",
            "leg_indexes": [0, 1],
            "net_market_value": 500.0,
            "capital_committed": 500.0,
            "maximum_loss": 500.0,
            "maximum_profit": 0.0,
            "width": 500.0,
            "classification_quality": "RECONSTRUCTED_MULTI_LEG",
        }],
        "positions": positions,
        "limits": {
            "max_symbol_pct": 10,
            "max_sector_pct": 25,
            "max_strategy_pct": 35,
            "max_portfolio_heat_pct": 20,
            "risk_per_trade_pct": 2,
        },
    }
    return {
        "snapshot_id": "M64-RISK-BASELINE",
        "portfolio_id": "PAPER-PRIMARY",
        "snapshot_timestamp": "2026-08-15T20:26:41+00:00",
        "broker_publication_id": "M63-PUB-CURRENT",
        "status": "READY",
        "health_score": 95.0,
        "net_liquidation": 3_900_000.0,
        "buying_power": 3_800_000.0,
        "capital_committed": 500.0,
        "open_risk": 500.0,
        "var_95": 12_491.978807607167,
        "expected_shortfall_95": 15_596.046268891372,
        "portfolio_heat_pct": 0.0128,
        "concentration_score": 100.0,
        "diversification_score": 0.0,
        "payload_json": payload,
    }


def _observed_four_minute_jitter(baseline: dict) -> dict:
    changed = deepcopy(baseline)
    changed["snapshot_id"] = "M64-RISK-JITTER"
    changed["snapshot_timestamp"] = "2026-08-15T20:30:51+00:00"
    changed["var_95"] = 12_491.950740317716
    changed["expected_shortfall_95"] = 15_596.011227305757
    payload = changed["payload_json"]
    payload["greeks"].update({
        "delta": 800.373309536517,
        "gamma": 38.01015212153242,
        "theta": -52.295069496883855,
        "vega": 451.8016966789034,
        "beta_weighted_delta": 310_993.17826239276,
    })
    payload["risk"]["var_95_one_day"] = 12_491.950740317716
    payload["risk"]["expected_shortfall_95_one_day"] = 15_596.011227305757
    payload["risk"]["stress"]["CORRELATION_BREAKDOWN"][
        "estimated_pnl"
    ] = -9_268.826942990903
    payload["risk"]["stress"]["DEALER_UNWIND"][
        "estimated_pnl"
    ] = -11_077.508008825795
    first = payload["positions"][0]
    first["implied_volatility"] = 0.21395593281802297
    first["greeks"].update({
        "delta": 51.98216219912651,
        "gamma": 12.458564344239347,
        "theta": -2.097430281131267,
        "vega": 6.029937332396786,
    })
    second = payload["positions"][1]
    second["implied_volatility"] = 0.2990634129672255
    second["greeks"].update({
        "delta": -63.77521989353402,
        "gamma": -2.528089117149767,
        "theta": 11.582132109941657,
        "vega": -19.410291777195138,
    })
    for position in payload["positions"]:
        position["expiration_guard"][
            "updated_at"
        ] = "2026-08-15T20:30:00+00:00"
    return changed


def test_observed_numeric_jitter_is_not_new_authority():
    baseline = _snapshot()
    jitter = _observed_four_minute_jitter(baseline)

    evaluation = PortfolioRiskAllocationService.materiality_evaluation(
        baseline,
        jitter,
    )
    assert evaluation["status"] == "EQUIVALENT"
    assert evaluation["suppressed_submaterial_change_count"] > 0
    assert (
        PortfolioRiskAllocationService.semantic_fingerprint(baseline)
        == PortfolioRiskAllocationService.semantic_fingerprint(jitter)
    )
    assert (
        PortfolioRiskAllocationService.state_integrity_fingerprint(baseline)
        != PortfolioRiskAllocationService.state_integrity_fingerprint(jitter)
    )


def test_structure_leg_indexes_are_replaced_by_stable_leg_identity():
    baseline = _snapshot()
    reordered = deepcopy(baseline)
    reordered["payload_json"]["positions"] = list(
        reversed(reordered["payload_json"]["positions"])
    )
    reordered["payload_json"]["structures"][0]["leg_indexes"] = [1, 0]

    assert (
        PortfolioRiskAllocationService.semantic_fingerprint(baseline)
        == PortfolioRiskAllocationService.semantic_fingerprint(reordered)
    )


def test_substantive_portfolio_and_risk_changes_cross_authority():
    baseline = _snapshot()
    baseline_fingerprint = (
        PortfolioRiskAllocationService.semantic_fingerprint(baseline)
    )
    mutations = []

    quantity = deepcopy(baseline)
    quantity["payload_json"]["positions"][0]["quantity"] = 2.0
    mutations.append(quantity)

    exit_date = deepcopy(baseline)
    exit_date["payload_json"]["positions"][0]["expiration_guard"][
        "exit_on_or_before_date"
    ] = "2026-09-16"
    mutations.append(exit_date)

    option_mark = deepcopy(baseline)
    option_mark["payload_json"]["positions"][0]["option_mark"] = 10.25
    mutations.append(option_mark)

    implied_volatility = deepcopy(baseline)
    implied_volatility["payload_json"]["positions"][0][
        "implied_volatility"
    ] = 0.24
    mutations.append(implied_volatility)

    aggregate_delta = deepcopy(baseline)
    aggregate_delta["payload_json"]["greeks"]["delta"] = 802.0
    mutations.append(aggregate_delta)

    exposure = deepcopy(baseline)
    exposure["payload_json"]["exposures"]["symbol"]["AAPL"] = 1_700
    mutations.append(exposure)

    buying_power = deepcopy(baseline)
    buying_power["buying_power"] = 3_799_800
    mutations.append(buying_power)

    for changed in mutations:
        assert (
            PortfolioRiskAllocationService.semantic_fingerprint(changed)
            != baseline_fingerprint
        )


def test_exact_integrity_detects_sub_material_tampering():
    baseline = _snapshot()
    baseline["payload_json"]["semantic_fingerprint"] = (
        PortfolioRiskAllocationService.semantic_fingerprint(baseline)
    )
    baseline_integrity = (
        PortfolioRiskAllocationService.state_integrity_fingerprint(baseline)
    )
    changed = deepcopy(baseline)
    changed["net_liquidation"] += 0.01

    assert (
        PortfolioRiskAllocationService.semantic_fingerprint(baseline)
        == PortfolioRiskAllocationService.semantic_fingerprint(changed)
    )
    assert (
        PortfolioRiskAllocationService.state_integrity_fingerprint(changed)
        != baseline_integrity
    )


def test_uncontracted_operational_telemetry_cannot_enter_authority():
    baseline = _snapshot()
    telemetry = deepcopy(baseline)
    telemetry["payload_json"]["producer_runtime_telemetry"] = {
        "observed_at": "2026-08-15T20:31:00+00:00",
        "worker_pid": 12345,
    }

    assert (
        PortfolioRiskAllocationService.semantic_fingerprint(baseline)
        == PortfolioRiskAllocationService.semantic_fingerprint(telemetry)
    )
    assert (
        PortfolioRiskAllocationService.state_integrity_fingerprint(baseline)
        != PortfolioRiskAllocationService.state_integrity_fingerprint(telemetry)
    )


def test_release_source_uses_explicit_material_authority_contract():
    root = Path(__file__).resolve().parents[1]
    service = (
        root / "src/trading_ai/portfolio_risk_allocation/service.py"
    ).read_text()
    orchestration = (
        root / "src/trading_ai/portfolio_risk_allocation/orchestration.py"
    ).read_text()

    for token in (
        "M64.2.4.7-BASELINE-MATERIAL-RISK-AUTHORITY-1.0",
        "M64.2.4.7-EXACT-RISK-SNAPSHOT-INTEGRITY-1.0",
        "MATERIALITY_POLICY",
        "EXPIRATION_GUARD_SEMANTIC_FIELDS",
        "def semantic_projection",
        "def state_integrity_fingerprint",
        '"legs": legs',
    ):
        assert token in service
    assert "published_risk_integrity_fingerprint" in orchestration
    assert "M64.2.4.7-AUTHORITY-INPUT-FINGERPRINT-1.0" in orchestration

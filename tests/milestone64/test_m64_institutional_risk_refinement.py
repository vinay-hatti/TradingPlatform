from trading_ai.portfolio_risk_allocation.service import PortfolioRiskAllocationService


class DummyFactory:
    pass


def service():
    return PortfolioRiskAllocationService(DummyFactory())


def test_vertical_call_spread_is_reconstructed_as_one_structure():
    rows = [
        {"symbol":"KO","expiry":"20260918","right":"C","quantity":1.0,"strike":85.0,"multiplier":100.0,"market_value":355.0,"capital_committed":340.0,"strategy":"LONG_CALL","classification_quality":"INFERRED_SINGLE_LEG"},
        {"symbol":"KO","expiry":"20260918","right":"C","quantity":-1.0,"strike":90.0,"multiplier":100.0,"market_value":126.5,"capital_committed":96.0,"strategy":"SHORT_CALL","classification_quality":"INFERRED_SINGLE_LEG"},
    ]
    structures = service()._reconstruct_structures(rows)
    assert len(structures) == 1
    assert structures[0]["strategy"] == "BULL_CALL_SPREAD"
    assert structures[0]["maximum_loss"] >= 0
    assert structures[0]["maximum_profit"] >= 0
    service()._apply_structure_classification(rows, structures)
    assert all(row["strategy"] == "BULL_CALL_SPREAD" for row in rows)
    assert all(row["classification_quality"] == "RECONSTRUCTED_MULTI_LEG" for row in rows)


def test_industry_and_theme_fallbacks_are_governed():
    svc = service()
    assert svc._industry_label("WFC", "Financials", "UNKNOWN") == "Diversified Banks"
    assert svc._industry_label("XOM", "Energy", "UNKNOWN") == "Integrated Oil & Gas"
    assert svc._theme_label("USO", "Crude Oil") == "Crude Oil"


def test_advanced_stress_scenarios_are_present():
    rows = [{"sector":"Energy","market_value":100.0,"underlying_price":100.0,"greeks":{"delta":10.0,"gamma":1.0,"vega":5.0,"rho":1.0}}]
    scenarios = service()._stress_payload(rows, 100.0)
    for key in ("ENERGY_DOWN_10", "VOLATILITY_CRUSH_15", "CORRELATION_BREAKDOWN", "DEALER_UNWIND"):
        assert key in scenarios


def test_policy_version_identifies_institutional_refinement():
    assert service().POLICY_VERSION == "M64-PORTFOLIO-RISK-1.2"

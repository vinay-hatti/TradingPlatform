from trading_ai.portfolio_risk_allocation.service import PortfolioRiskAllocationService


class DummyFactory:
    pass


def service():
    return PortfolioRiskAllocationService(DummyFactory())


def sample_rows():
    return [{
        "symbol": "TEST",
        "sector": "INFORMATION TECHNOLOGY",
        "market_value": 500.0,
        "underlying_price": 100.0,
        "implied_volatility": 0.30,
        "realized_volatility_20d": 0.25,
        "greeks": {"delta": 50.0, "gamma": 2.0, "theta": -4.0, "vega": 20.0, "rho": 5.0},
    }]


def test_delta_gamma_vega_var_is_economic_and_nonzero():
    var95, es95 = service()._delta_gamma_vega_var(sample_rows())
    assert var95 > 0
    assert es95 > var95


def test_stress_uses_signed_greeks_and_sector_scope():
    scenarios = service()._stress_payload(sample_rows(), 500.0)
    assert scenarios["SPY_DOWN_5"]["estimated_pnl"] < 0
    assert scenarios["TECH_DOWN_10"]["estimated_pnl"] < 0
    assert scenarios["VIX_UP_20"]["estimated_pnl"] > 0
    assert "JOINT_EQUITY_IV_SHOCK" in scenarios


def test_policy_version_identifies_enriched_engine():
    assert service().POLICY_VERSION == "M64-PORTFOLIO-RISK-1.2"

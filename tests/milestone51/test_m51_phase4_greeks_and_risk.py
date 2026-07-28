from trading_ai.paper_trading.automated_portfolio_management import (
    AutomatedPortfolioManagementEngine,
    PortfolioPositionInput,
)


def test_option_greeks_aggregate():
    engine = AutomatedPortfolioManagementEngine()
    rows = [
        PortfolioPositionInput(
            position_id="P1",
            symbol="AAPL",
            security_type="OPT",
            direction="LONG",
            quantity=2,
            average_entry_price=5,
            current_price=6,
            market_value=1200,
            unrealized_pnl=200,
            delta=0.5,
            gamma=0.02,
            theta=-0.1,
            vega=0.15,
            rho=0.01,
            multiplier=100,
        )
    ]
    greeks = engine.greeks(rows, 100000)
    assert greeks.delta == 100
    assert greeks.gamma == 4
    assert greeks.theta == -20
    assert greeks.vega == 30


def test_symbol_concentration_creates_breach_and_recommendation():
    engine = AutomatedPortfolioManagementEngine()
    rows = [
        PortfolioPositionInput(
            position_id="P1",
            symbol="AAPL",
            security_type="STK",
            direction="LONG",
            quantity=1,
            average_entry_price=30000,
            current_price=30000,
            market_value=30000,
            unrealized_pnl=0,
            sector="TECHNOLOGY",
            industry="HARDWARE",
        )
    ]
    state = engine.state(
        rows,
        {"cash": 70000, "net_liquidation_value": 100000},
    )
    greeks = engine.greeks(rows, 100000)
    symbol = engine.exposures(rows, 100000, "symbol")
    sector = engine.exposures(rows, 100000, "sector")
    industry = engine.exposures(rows, 100000, "industry")
    breaches = engine.risk_breaches(
        state, greeks, symbol, sector, industry, drawdown_pct=0
    )
    assert any(row.code == "SYMBOL_CONCENTRATION" for row in breaches)
    recs = engine.recommendations(breaches)
    assert any(row.action == "REDUCE_POSITION" for row in recs)

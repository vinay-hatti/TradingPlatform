from trading_ai.paper_trading.automated_portfolio_management import (
    AutomatedPortfolioManagementEngine,
    PortfolioPositionInput,
)


def position(symbol, value, sector):
    return PortfolioPositionInput(
        position_id=symbol,
        symbol=symbol,
        security_type="STK",
        direction="LONG",
        quantity=1,
        average_entry_price=value,
        current_price=value,
        market_value=value,
        unrealized_pnl=0,
        sector=sector,
    )


def test_state_and_sector_exposure_are_computed():
    engine = AutomatedPortfolioManagementEngine()
    rows = [
        position("AAPL", 20000, "TECHNOLOGY"),
        position("MSFT", 10000, "TECHNOLOGY"),
        position("JPM", 5000, "FINANCIALS"),
    ]
    state = engine.state(
        rows,
        {
            "portfolio_id": "PAPER-PRIMARY",
            "cash": 65000,
            "buying_power": 130000,
            "net_liquidation_value": 100000,
        },
    )
    sectors = engine.exposures(rows, 100000, "sector")
    assert state.gross_exposure_pct == 35
    assert sectors[0].key == "TECHNOLOGY"
    assert sectors[0].capital_pct == 30

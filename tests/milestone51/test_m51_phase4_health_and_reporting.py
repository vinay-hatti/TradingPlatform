from trading_ai.paper_trading.automated_portfolio_management import (
    AutomatedPortfolioManagementService,
    render_portfolio_markdown,
)


def test_service_generates_health_and_report():
    lifecycle = {
        "portfolio_id": "PAPER-PRIMARY",
        "positions": [{
            "position_id": "P1",
            "symbol": "AAPL",
            "security_type": "STK",
            "direction": "LONG",
            "quantity": 10,
            "average_entry_price": 100,
            "status": "OPEN",
            "metadata": {"sector": "TECHNOLOGY", "industry": "HARDWARE"},
        }],
    }
    result = AutomatedPortfolioManagementService().execute(
        lifecycle,
        {"AAPL": {"price": 110, "sector": "TECHNOLOGY", "industry": "HARDWARE"}},
        {
            "portfolio_id": "PAPER-PRIMARY",
            "cash": 98900,
            "buying_power": 197800,
            "net_liquidation_value": 100000,
            "daily_pnl": 100,
        },
    )
    assert 0 <= result.health["overall"] <= 100
    markdown = render_portfolio_markdown(result.to_dict())
    assert "Portfolio Risk Report" in markdown
    assert "Net liquidation value" in markdown

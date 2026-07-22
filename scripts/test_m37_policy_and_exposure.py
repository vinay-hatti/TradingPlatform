from trading_ai.portfolio_risk_management.exposure_service import PortfolioRiskExposureService
from trading_ai.portfolio_risk_management.policy import PortfolioRiskPolicy

policy = PortfolioRiskPolicy()
policy.validate()
registry = {
    "net_liquidation_value": 100000.0,
    "cash_balance": 70000.0,
    "positions": [
        {"position_id": "P1", "status": "OPEN", "symbol": "AAPL", "sector": "TECH", "strategy_type": "BULL_CALL_SPREAD", "direction": "BULLISH", "correlation_group": "MEGA_CAP", "capital_committed": 20000.0, "maximum_loss": 20000.0, "delta": 50, "gamma": 2, "theta": -4, "vega": 20, "rho": 1, "metadata": {"option_volume": 100, "open_interest": 1000, "spread_pct": 0.05}},
        {"position_id": "P2", "status": "OPEN", "symbol": "MSFT", "sector": "TECH", "strategy_type": "BULL_PUT_SPREAD", "direction": "BULLISH", "correlation_group": "MEGA_CAP", "capital_committed": 10000.0, "maximum_loss": 8000.0, "delta": 25, "gamma": 1, "theta": 3, "vega": -10, "rho": 1, "metadata": {"option_volume": 1, "open_interest": 5, "spread_pct": 0.5}},
    ],
}
result = PortfolioRiskExposureService().evaluate(registry)
assert result["capital_committed"] == 30000.0
assert result["capital_utilization_pct"] == 30.0
assert result["concentration"]["largest_sector_pct"] == 100.0
assert result["liquidity"]["illiquid_capital"] == 10000.0
print("Milestone 37 policy and exposure assertions passed.")

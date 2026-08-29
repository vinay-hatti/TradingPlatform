from trading_ai.portfolio_risk_management.policy import PortfolioRiskPolicy
from trading_ai.portfolio_risk_management.service import PortfolioRiskManagementService
from trading_ai.portfolio_risk_management.serialization import write_json_atomic
from pathlib import Path
from tempfile import TemporaryDirectory

with TemporaryDirectory() as tmp:
    registry = Path(tmp) / "registry.json"
    write_json_atomic(registry, {
        "account": {"portfolio_id": "PRIMARY"}, "net_liquidation_value": 100000.0, "cash_balance": 10000.0,
        "positions": [{"position_id": "P1", "status": "OPEN", "symbol": "AAPL", "sector": "TECH", "strategy_type": "LONG_CALL", "direction": "BULLISH", "correlation_group": "TECH", "capital_committed": 90000.0, "maximum_loss": 90000.0, "delta": 800, "gamma": 150, "theta": -600, "vega": 1200, "rho": 1100}],
    })
    assessment = PortfolioRiskManagementService(PortfolioRiskPolicy()).assess(registry)
    assert assessment.status in {"HIGH_RISK", "CRITICAL"}
    assert assessment.trading_control in {"REDUCE_ONLY", "BLOCK_NEW_RISK"}
    assert len(assessment.breaches) >= 5
    assert len(assessment.stress_results) == 5
print("Milestone 37 stress and breach assertions passed.")

from pathlib import Path
from tempfile import TemporaryDirectory
from trading_ai.portfolio_risk_management.repository import PortfolioRiskRepository
from trading_ai.portfolio_risk_management.serialization import write_json_atomic, read_json
from trading_ai.portfolio_risk_management.service import PortfolioRiskManagementService

with TemporaryDirectory() as tmp:
    root = Path(tmp)
    registry = root / "registry.json"
    write_json_atomic(registry, {"account": {"portfolio_id": "PRIMARY"}, "net_liquidation_value": 100000.0, "cash_balance": 100000.0, "positions": []})
    assessment = PortfolioRiskManagementService().assess(registry)
    repo = PortfolioRiskRepository(root / "history.json", root / "breaches.json", root / "actions.json")
    repo.persist(assessment)
    repo.persist(assessment)
    assert len(read_json(root / "history.json")["assessments"]) == 1
print("Milestone 37 persistence and idempotency assertions passed.")

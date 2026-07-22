from pathlib import Path
from tempfile import TemporaryDirectory
from trading_ai.portfolio_risk_management.serialization import write_json_atomic, read_json
from trading_ai.portfolio_risk_management.workflow_service import Milestone37WorkflowService

with TemporaryDirectory() as tmp:
    root = Path(tmp)
    registry = root / "registry.json"
    output = root / "reports"
    write_json_atomic(registry, {"account": {"portfolio_id": "PRIMARY"}, "net_liquidation_value": 100000.0, "cash_balance": 100000.0, "positions": []})
    result = Milestone37WorkflowService().run(registry, output)
    assert result["status"] == "COMPLETE"
    assert (output / "milestone37_closure.json").exists()
    assert (output / "milestone37_closure.html").exists()
    assert read_json(output / "execution_risk_control.json")["allow_new_risk"] is True
print("Milestone 37 workflow and reporting assertions passed.")

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from trading_ai.portfolio_management.lifecycle_service import PositionLifecycleReconciliationService
from trading_ai.portfolio_management.service import PortfolioRegistryService


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        registry = PortfolioRegistryService(root / "registry.json")
        registry.initialize("Test", 100000)
        registry.register_position(
            position_id="POSITION-1", symbol="AMZN", strategy_id="AMZN:TEST",
            strategy_type="BULL_CALL_SPREAD", direction="CALL", quantity=1,
            entry_price=1.30, capital_committed=130,
        )
        artifact = root / "performance.json"
        artifact.write_text(json.dumps({"positions": [{
            "position_id": "POSITION-1", "symbol": "AMZN",
            "strategy_id": "AMZN:TEST", "status": "OPEN",
            "current_debit": 1.50,
        }]}))
        service = PositionLifecycleReconciliationService(registry, root / "journal.json")
        result = service.reconcile_performance_artifact(artifact)[0]
        assert result.repaired and result.action == "UPDATED_MARK"
        snapshot = registry.load_snapshot()
        assert snapshot.total_unrealized_pnl == 20.0
        duplicate = service.reconcile_performance_artifact(artifact)[0]
        assert duplicate.duplicate and duplicate.status == "DUPLICATE_EVENT"
        assert len(service.load_journal().events) == 1
    print("Milestone 36 Phase 1 Step 3 reconciliation assertions passed.")

if __name__ == "__main__":
    main()

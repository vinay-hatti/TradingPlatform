from __future__ import annotations

import json
import tempfile
from pathlib import Path

from trading_ai.portfolio_management.ingestion_service import PortfolioArtifactIngestionService
from trading_ai.portfolio_management.service import PortfolioRegistryService


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = PortfolioRegistryService(root / "registry.json")
        registry.initialize("Test", 100000)
        service = PortfolioArtifactIngestionService(registry, root / "intake.json")
        lifecycle = root / "lifecycle.json"
        lifecycle.write_text(json.dumps({
            "order": {
                "order_id": "ORDER-1", "status": "FILLED",
                "strategy_id": "AMZN:TEST:VERTICAL", "symbol": "AMZN",
                "direction": "CALL", "strategy_type": "BULL_CALL_SPREAD",
                "quantity": 1, "average_fill_debit": 1.3,
            },
            "position": {
                "position_id": "POSITION-1", "status": "OPEN",
                "strategy_id": "AMZN:TEST:VERTICAL", "symbol": "AMZN",
                "direction": "CALL", "strategy_type": "BULL_CALL_SPREAD",
                "quantity": 1, "entry_debit": 1.3,
                "max_loss": 1.3, "max_profit": 3.7, "legs": [],
            },
        }))
        first = service.ingest_paper_trade_lifecycle(lifecycle)
        second = service.ingest_paper_trade_lifecycle(lifecycle)
        snapshot = registry.load_snapshot()
        assert first.imported and first.position_id == "POSITION-1"
        assert second.duplicate
        assert snapshot.open_position_count == 1
        assert snapshot.total_capital_committed == 130.0
        assert snapshot.cash_balance == 99870.0
    print("Milestone 36 Phase 1 Step 2 lifecycle-ingestion assertions passed.")


if __name__ == "__main__":
    main()

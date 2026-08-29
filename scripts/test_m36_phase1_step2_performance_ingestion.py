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
        registry.register_position(
            position_id="POSITION-1", symbol="AMZN", strategy_id="AMZN:TEST",
            strategy_type="BULL_CALL_SPREAD", direction="CALL", quantity=1,
            entry_price=1.3, capital_committed=130, maximum_loss=130,
            maximum_profit=370,
        )
        service = PortfolioArtifactIngestionService(registry, root / "intake.json")
        artifact = root / "performance.json"
        artifact.write_text(json.dumps({"positions": [{
            "position_id": "POSITION-1", "symbol": "AMZN",
            "strategy_id": "AMZN:TEST", "status": "OPEN",
            "current_debit": 1.5,
        }]}))
        results = service.ingest_performance(artifact)
        snapshot = registry.load_snapshot()
        assert results[0].marked
        assert snapshot.total_unrealized_pnl == 20.0
        assert snapshot.net_liquidation_value == 100020.0
    print("Milestone 36 Phase 1 Step 2 performance-ingestion assertions passed.")


if __name__ == "__main__":
    main()

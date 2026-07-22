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
        artifact = root / "decision.json"
        artifact.write_text(json.dumps({
            "symbol": "AMZN",
            "direction": "CALL",
            "decision": "APPROVE",
            "selected_strategy_id": "AMZN:TEST:VERTICAL",
            "selected_strategy": {
                "strategy_id": "AMZN:TEST:VERTICAL",
                "strategy_type": "BULL_CALL_SPREAD",
                "debit": 1.2,
                "max_loss": 1.2,
                "max_profit": 3.8,
                "reward_risk_ratio": 3.16,
                "institutional_score": 78.0,
            },
            "paper_trade_ready": False,
            "paper_trade_payload": {"execution_status": "QUOTE_REFRESH_REQUIRED"},
            "warnings": ["QUOTE_REFRESH_REQUIRED_BEFORE_PAPER_TRADE"],
        }))
        first = service.ingest_institutional_decision(artifact)
        second = service.ingest_institutional_decision(artifact)
        snapshot = service.load_intake()
        assert first.imported and first.status == "QUOTE_REFRESH_REQUIRED"
        assert second.duplicate
        assert len(snapshot.records) == 1
        assert registry.load_snapshot().open_position_count == 0
    print("Milestone 36 Phase 1 Step 2 decision-ingestion assertions passed.")


if __name__ == "__main__":
    main()

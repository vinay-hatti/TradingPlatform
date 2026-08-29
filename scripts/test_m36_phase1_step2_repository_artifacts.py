from __future__ import annotations

import tempfile
from pathlib import Path

from trading_ai.portfolio_management.ingestion_service import PortfolioArtifactIngestionService
from trading_ai.portfolio_management.service import PortfolioRegistryService


def main() -> None:
    dashboard = Path("reports/m35/phase5/dashboard")
    decision = dashboard / "institutional_decision/amzn_call_institutional_decision.json"
    lifecycle = dashboard / "paper_trade/amzn_paper-f91616edd57044c8_lifecycle.json"
    performance = dashboard / "performance/paper_trade_performance.json"
    if not all(path.exists() for path in (decision, lifecycle, performance)):
        print("Repository artifact integration test skipped: M35 sample artifacts unavailable.")
        return
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = PortfolioRegistryService(root / "registry.json")
        registry.initialize("Repository Integration", 100000)
        service = PortfolioArtifactIngestionService(registry, root / "intake.json")
        results = service.ingest_dashboard_directory(dashboard)
        snapshot = registry.load_snapshot()
        intake = service.load_intake()
        assert results
        assert snapshot.open_position_count == 1
        assert snapshot.total_capital_committed == 130.0
        assert snapshot.total_unrealized_pnl == 20.0
        assert len(intake.records) == 1
        assert intake.records[0].intake_status == "EXECUTED"
    print("Milestone 36 Phase 1 Step 2 repository-artifact assertions passed.")


if __name__ == "__main__":
    main()

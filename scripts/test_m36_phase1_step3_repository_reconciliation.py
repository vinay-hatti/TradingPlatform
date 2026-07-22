from __future__ import annotations

import tempfile
from pathlib import Path

from trading_ai.portfolio_management.ingestion_service import PortfolioArtifactIngestionService
from trading_ai.portfolio_management.lifecycle_service import PositionLifecycleReconciliationService
from trading_ai.portfolio_management.service import PortfolioRegistryService


def main() -> None:
    dashboard = Path("reports/m35/phase5/dashboard")
    assert dashboard.exists()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        registry = PortfolioRegistryService(root / "registry.json")
        registry.initialize("Repository Test", 100000)
        ingestion = PortfolioArtifactIngestionService(registry, root / "intake.json")
        ingestion.ingest_dashboard_directory(dashboard)
        service = PositionLifecycleReconciliationService(registry, root / "journal.json")
        results = service.reconcile_dashboard_directory(dashboard)
        assert results
        assert not [r for r in results if r.status == "EXCEPTION"]
        snapshot = registry.load_snapshot()
        assert snapshot.open_position_count == 1
        assert snapshot.total_unrealized_pnl == 20.0
        journal = service.load_journal()
        assert journal.events
        assert journal.to_dict()["unresolved_exception_count"] == 0
    print("Milestone 36 Phase 1 Step 3 repository reconciliation assertions passed.")

if __name__ == "__main__":
    main()

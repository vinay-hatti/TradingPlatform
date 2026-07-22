from __future__ import annotations

import tempfile
from pathlib import Path

from trading_ai.portfolio_management.service import PortfolioRegistryService
from trading_ai.portfolio_management.workflow_service import PortfolioPhaseWorkflowService


class FakeDatabaseSyncService:
    def synchronize(self, **kwargs):
        Path(kwargs["report_file"]).parent.mkdir(parents=True, exist_ok=True)
        Path(kwargs["report_file"]).write_text('{"status":"COMPLETE"}', encoding="utf-8")
        return {"status": "COMPLETE"}


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry_file = root / "registry.json"
        PortfolioRegistryService(registry_file).initialize("Test", 100000)
        workflow = PortfolioPhaseWorkflowService(
            registry_file=registry_file, intake_file=root / "intake.json",
            lifecycle_file=root / "lifecycle.json", snapshot_directory=root / "snapshots",
            exposure_file=root / "exposure.json", audit_file=root / "audit.json",
            database_report_file=root / "database.json", report_json_file=root / "closure.json",
            report_html_file=root / "closure.html", session_factory=lambda: None,
        )
        workflow.database = FakeDatabaseSyncService()
        dashboard = root / "dashboard"
        dashboard.mkdir()
        result = workflow.run(dashboard, sync_database=True)
        assert result["database_status"] == "COMPLETE"
        assert Path(result["report_json"]).exists()
        assert Path(result["report_html"]).exists()
        assert result["readiness"]["status"] == "READY"
    print("Milestone 36 Phase 1 Step 6 unified-workflow assertions passed.")


if __name__ == "__main__":
    main()

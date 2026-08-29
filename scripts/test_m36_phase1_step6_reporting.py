from __future__ import annotations

import json
import tempfile
from pathlib import Path

from trading_ai.portfolio_management.reporting_service import PortfolioPhaseReportingService
from trading_ai.portfolio_management.service import PortfolioRegistryService
from trading_ai.portfolio_management.snapshot_service import PortfolioSnapshotService


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry_file = root / "registry.json"
        audit_file = root / "audit.json"
        exposure_file = root / "exposure.json"
        snapshot_dir = root / "snapshots"
        lifecycle_file = root / "lifecycle.json"
        database_file = root / "database.json"
        report_json = root / "report.json"
        report_html = root / "report.html"
        registry = PortfolioRegistryService(registry_file)
        registry.initialize("Test", 100000)
        PortfolioSnapshotService(registry, snapshot_dir, exposure_file, audit_file).create_snapshot("TEST")
        lifecycle_file.write_text(json.dumps({"unresolved_exception_count": 0}), encoding="utf-8")
        database_file.write_text(json.dumps({"status": "COMPLETE"}), encoding="utf-8")
        report = PortfolioPhaseReportingService(
            registry_file=registry_file, snapshot_directory=snapshot_dir,
            exposure_file=exposure_file, audit_file=audit_file,
            lifecycle_file=lifecycle_file, database_report_file=database_file,
        ).write_report(report_json, report_html)
        assert report.status == "READY"
        assert report.readiness.checks["database_sync_complete"]
        assert report_json.exists() and report_html.exists()
        assert "Milestone 36 Phase 1" in report_html.read_text(encoding="utf-8")
    print("Milestone 36 Phase 1 Step 6 reporting assertions passed.")


if __name__ == "__main__":
    main()

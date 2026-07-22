from __future__ import annotations

from pathlib import Path
from typing import Callable

from .database_service import PortfolioDatabaseSyncService
from .ingestion_service import PortfolioArtifactIngestionService
from .lifecycle_service import PositionLifecycleReconciliationService
from .reporting_service import PortfolioPhaseReportingService
from .service import PortfolioRegistryService
from .snapshot_service import PortfolioSnapshotService


class PortfolioPhaseWorkflowService:
    def __init__(self, *, registry_file: Path, intake_file: Path, lifecycle_file: Path,
                 snapshot_directory: Path, exposure_file: Path, audit_file: Path,
                 database_report_file: Path, report_json_file: Path, report_html_file: Path,
                 session_factory: Callable | None = None) -> None:
        self.registry = PortfolioRegistryService(registry_file)
        self.ingestion = PortfolioArtifactIngestionService(self.registry, intake_file)
        self.lifecycle = PositionLifecycleReconciliationService(self.registry, lifecycle_file)
        self.snapshots = PortfolioSnapshotService(self.registry, snapshot_directory, exposure_file, audit_file)
        self.database = PortfolioDatabaseSyncService(session_factory=session_factory)
        self.reporting = PortfolioPhaseReportingService(
            registry_file=registry_file, snapshot_directory=snapshot_directory,
            exposure_file=exposure_file, audit_file=audit_file,
            lifecycle_file=lifecycle_file, database_report_file=database_report_file,
            session_factory=session_factory,
        )
        self.registry_file = registry_file
        self.snapshot_directory = snapshot_directory
        self.audit_file = audit_file
        self.database_report_file = database_report_file
        self.report_json_file = report_json_file
        self.report_html_file = report_html_file

    def run(self, dashboard_dir: Path, *, auto_repair: bool = True, sync_database: bool = True) -> dict:
        ingested = self.ingestion.ingest_dashboard_directory(dashboard_dir)
        reconciled = self.lifecycle.reconcile_dashboard_directory(dashboard_dir, auto_repair=auto_repair)
        snapshot = self.snapshots.create_snapshot(event_type="PHASE_1_WORKFLOW")
        database = {"status": "SKIPPED"}
        if sync_database:
            database = self.database.synchronize(
                registry_file=self.registry_file,
                snapshot_directory=self.snapshot_directory,
                audit_file=self.audit_file,
                report_file=self.database_report_file,
            )
        report = self.reporting.write_report(self.report_json_file, self.report_html_file)
        return {
            "status": report.status,
            "portfolio_id": report.portfolio_id,
            "ingestion_results": len(ingested),
            "reconciliation_results": len(reconciled),
            "snapshot_id": snapshot.snapshot_id,
            "database_status": database.get("status", "UNKNOWN"),
            "report_json": str(self.report_json_file),
            "report_html": str(self.report_html_file),
            "readiness": report.readiness.to_dict(),
        }

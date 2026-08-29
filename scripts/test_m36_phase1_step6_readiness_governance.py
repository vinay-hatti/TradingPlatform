from __future__ import annotations

import tempfile
from pathlib import Path

from trading_ai.portfolio_management.reporting_service import PortfolioPhaseReportingService


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        service = PortfolioPhaseReportingService(
            registry_file=root / "registry.json", snapshot_directory=root / "snapshots",
            exposure_file=root / "exposure.json", audit_file=root / "audit.json",
            lifecycle_file=root / "lifecycle.json", database_report_file=root / "database.json",
        )
        readiness = service.evaluate_readiness(
            registry={"account": {"portfolio_id": "PRIMARY"}, "cash_balance": 100.0,
                      "net_liquidation_value": 100.0, "open_position_count": 0,
                      "closed_position_count": 0},
            exposure={"portfolio_id": "PRIMARY", "warnings": []},
            lifecycle={"unresolved_exception_count": 1},
            audit={"records": []}, database={"status": "SKIPPED"},
        )
        assert readiness.status == "NOT_READY"
        assert "UNRESOLVED_LIFECYCLE_EXCEPTIONS:1" in readiness.warnings
        assert "DATABASE_SYNC_NOT_COMPLETE" in readiness.warnings
        assert not readiness.checks["audit_history_available"]
    print("Milestone 36 Phase 1 Step 6 readiness-governance assertions passed.")


if __name__ == "__main__":
    main()

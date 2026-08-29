from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from trading_ai.ui.adapters.artifact_sources import RepositoryArtifactAdapters
from trading_ai.ui.api.reporting_audit import service as reporting_dependency
from trading_ai.ui.app import create_app
from trading_ai.ui.services.reporting_audit_service import ReportingAuditService


def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        reports = root / "reports"
        audit_dir = reports / "audit"
        governance_dir = reports / "governance"
        execution_dir = reports / "execution"
        audit_dir.mkdir(parents=True)
        governance_dir.mkdir(parents=True)
        execution_dir.mkdir(parents=True)

        governance_report = governance_dir / "walk_forward_governance.html"
        governance_report.write_text(
            "<html>Walk-Forward Parameter Governance</html>",
            encoding="utf-8",
        )
        execution_report = execution_dir / "execution_quality.json"
        execution_report.write_text(
            json.dumps({"fill_rate_pct": 92}),
            encoding="utf-8",
        )

        expected_hash = hashlib.sha256(
            governance_report.read_bytes()
        ).hexdigest()
        (reports / "checksums.json").write_text(
            json.dumps({
                str(governance_report.relative_to(root)): expected_hash
            }),
            encoding="utf-8",
        )

        (audit_dir / "audit_log.json").write_text(
            json.dumps({
                "events": [
                    {
                        "event_id": "A1",
                        "occurred_at": "2026-07-18T15:00:00+00:00",
                        "event_type": "ORDER_GOVERNANCE",
                        "severity": "INFO",
                        "actor": "execution-service",
                        "entity_type": "order",
                        "entity_id": "O1",
                        "action": "VALIDATE",
                        "outcome": "APPROVED",
                        "message": "Order validation passed.",
                    },
                    {
                        "event_id": "A2",
                        "occurred_at": "2026-07-18T15:01:00+00:00",
                        "event_type": "RISK_POLICY",
                        "severity": "WARNING",
                        "actor": "risk-service",
                        "entity_type": "decision",
                        "entity_id": "D1",
                        "action": "AUTHORIZE",
                        "outcome": "REJECTED",
                        "message": "Risk budget exceeded.",
                    },
                ]
            }),
            encoding="utf-8",
        )

        service = ReportingAuditService(
            RepositoryArtifactAdapters(root),
            stale_after_seconds=999999999,
        )
        direct = service.get()

        assert direct.available is True
        assert direct.summary.report_count >= 3
        assert direct.summary.audit_event_count == 2
        assert direct.summary.warning_event_count == 1
        assert direct.summary.verified_report_count == 1
        assert direct.summary.failed_integrity_count == 0
        assert any(
            item.control == "Artifact integrity"
            and item.status == "PASS"
            for item in direct.governance
        )
        assert any(
            item.control == "Rejected or failed action review"
            and item.status == "WARNING"
            for item in direct.governance
        )

        app = create_app()
        app.dependency_overrides[reporting_dependency] = lambda: service
        response = TestClient(app).get("/api/v1/reporting-audit")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["summary"]["audit_event_count"] == 2
        assert payload["summary"]["verified_report_count"] == 1
        app.dependency_overrides.clear()

    print(
        "All Milestone 31 Phase 7 Institutional Reporting and "
        "Audit Center assertions passed."
    )


if __name__ == "__main__":
    main()

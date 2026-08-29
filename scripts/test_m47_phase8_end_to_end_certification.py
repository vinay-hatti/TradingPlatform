from __future__ import annotations

import json
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from trading_ai.certification import CertificationPolicy, Milestone47CertificationService
from trading_ai.reporting import ReportingContext, write_report_manifest


class Result:
    def __init__(self, *, row=None, scalar=None):
        self.row = row
        self.scalar = scalar
    def mappings(self): return self
    def one_or_none(self): return self.row
    def scalar_one_or_none(self): return self.scalar


class Session:
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, statement, params=None):
        sql = str(statement)
        if "FROM alembic_version" in sql:
            return Result(scalar="m47_002")
        if "FROM market_ingestion_publication" in sql:
            return Result(row={
                "publication_name": "current_market_state",
                "run_id": "readiness-test",
                "readiness_status": "DEGRADED",
                "scanner_ready": True,
                "decision_context_ready": True,
                "option_snapshot_id": "polygon-test",
                "published_at": "2026-07-25T23:52:16Z",
                "as_of_date": "2026-07-23",
                "market_intelligence_timestamp": "2026-07-25T23:49:40Z",
                "option_snapshot_timestamp": "2026-07-25T17:45:07Z",
            })
        if "FROM scanner_lineage_run" in sql:
            return Result(row={
                "scanner_run_id": "scanner-test",
                "publication_name": "current_market_state",
                "ingestion_run_id": "readiness-test",
                "publication_status": "DEGRADED",
                "option_snapshot_id": "polygon-test",
                "market_state_hash": "abc123",
                "scanner_version": "m47.phase6.v1",
                "candidate_count": 2,
                "status": "READY",
                "completed_at": "2026-07-25T20:11:08-05:00",
            })
        if "COUNT(*) FROM scanner_candidate_lineage" in sql:
            return Result(scalar=2)
        if "FROM institutional_decision_lineage_run" in sql:
            return Result(row={
                "decision_run_id": "decision-test",
                "publication_name": "current_market_state",
                "ingestion_run_id": "readiness-test",
                "publication_status": "DEGRADED",
                "option_snapshot_id": "polygon-test",
                "market_state_hash": "abc123",
                "decision_engine_version": "m47.phase6.v1",
                "policy_version": "published-state.v1",
                "decision_count": 1,
                "status": "READY",
                "completed_at": "2026-07-25T20:12:00-05:00",
            })
        if "FROM historical_replay_run" in sql:
            return Result(row={
                "replay_run_id": "replay-test",
                "source_scanner_run_id": "scanner-test",
                "source_decision_run_id": "decision-test",
                "replay_mode": "SNAPSHOT",
                "status": "READY",
                "mismatch_count": 0,
                "completed_at": "2026-07-25T20:13:00-05:00",
            })
        raise AssertionError(sql)


def factory(): return Session()


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        artifact = root / "sample.json"
        artifact.write_text('{"ok": true}', encoding="utf-8")
        source_manifest = write_report_manifest(
            root / "source_manifest.json",
            context=ReportingContext(publication_name="current_market_state"),
            artifacts=[artifact],
            report_type="test",
            extra={
                "db_datetime": datetime(2026, 7, 25, 20, 11, 8, tzinfo=timezone.utc),
                "market_date": date(2026, 7, 23),
                "coverage": Decimal("99.5082"),
                "nested": {"completed_at": datetime(2026, 7, 25, 20, 13, tzinfo=timezone.utc)},
            },
        )
        source_payload = json.loads(source_manifest.read_text(encoding="utf-8"))
        assert source_payload["metadata"]["db_datetime"] == "2026-07-25T20:11:08+00:00"
        assert source_payload["metadata"]["market_date"] == "2026-07-23"
        assert source_payload["metadata"]["coverage"] == 99.5082

        service = Milestone47CertificationService(
            factory,
            policy=CertificationPolicy(
                require_decision_lineage=True,
                require_replay_history=True,
                require_manifest_integrity=True,
            ),
        )
        result = service.run(report_manifest_paths=[source_manifest])
        assert result.status == "CERTIFIED"
        assert result.passed
        assert not result.blocking_failures
        assert all(check.status == "PASSED" for check in result.checks)

        paths = service.export(result, root / "certification")
        payload = json.loads(paths["json"].read_text(encoding="utf-8"))
        manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
        html = paths["html"].read_text(encoding="utf-8")
        assert payload["status"] == "CERTIFIED"
        assert manifest["report_type"] == "milestone47_end_to_end_certification"
        assert len(manifest["artifacts"]) == 2
        assert "Milestone 47 End-to-End Certification" in html
        assert "REPORT_MANIFEST_INTEGRITY" in html

        artifact.write_text('{"ok": false}', encoding="utf-8")
        failed = service.run(report_manifest_paths=[source_manifest])
        assert failed.status == "FAILED"
        assert "REPORT_MANIFEST_INTEGRITY" in {x.code for x in failed.blocking_failures}

    print("Milestone 47 Phase 8 end-to-end certification assertions passed.")


if __name__ == "__main__":
    main()

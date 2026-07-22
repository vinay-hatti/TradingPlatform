from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

from trading_ai.database.repositories.portfolio_management import PortfolioManagementRepository
from .profile import utc_now_iso
from .serialization import read_json, write_json_atomic


class PortfolioDatabaseSyncService:
    def __init__(self, session_factory: Callable | None = None) -> None:
        if session_factory is None:
            from trading_ai.database.session import create_session
            session_factory = create_session
        self.session_factory = session_factory

    def synchronize(
        self,
        *,
        registry_file: Path,
        snapshot_directory: Path,
        audit_file: Path,
        report_file: Path | None = None,
    ) -> dict:
        registry = read_json(registry_file)
        if not registry:
            raise FileNotFoundError(registry_file)
        portfolio_id = registry["account"]["portfolio_id"]
        fingerprint = hashlib.sha256(json.dumps(registry, sort_keys=True).encode()).hexdigest()
        started_at = utc_now_iso()
        counts = {"accounts_upserted": 1, "positions_upserted": 0, "ledger_entries_upserted": 0, "snapshots_upserted": 0, "audit_records_upserted": 0}
        warnings: list[str] = []

        session = self.session_factory()
        try:
            repo = PortfolioManagementRepository(session)
            repo.upsert_account(registry["account"])
            for item in registry.get("positions", []):
                repo.upsert_position(item)
                counts["positions_upserted"] += 1
            for item in registry.get("cash_ledger", []):
                repo.upsert_ledger_entry(item)
                counts["ledger_entries_upserted"] += 1

            for path in sorted(snapshot_directory.glob("*.json")) if snapshot_directory.exists() else []:
                payload = read_json(path)
                if payload and payload.get("portfolio_id") == portfolio_id:
                    repo.upsert_snapshot(payload)
                    counts["snapshots_upserted"] += 1

            audit = read_json(audit_file) if audit_file.exists() else {}
            for item in audit.get("records", []):
                repo.upsert_audit_record(item)
                counts["audit_records_upserted"] += 1

            completed_at = utc_now_iso()
            sync_id = "SYNC-" + hashlib.sha256(f"{portfolio_id}|{fingerprint}|{completed_at}".encode()).hexdigest()[:20].upper()
            report = {
                "sync_id": sync_id,
                "portfolio_id": portfolio_id,
                "started_at": started_at,
                "completed_at": completed_at,
                "status": "COMPLETE",
                "registry_fingerprint": fingerprint,
                **counts,
                "warnings": warnings,
            }
            sync_payload = {key: value for key, value in report.items() if key != "warnings"}
            sync_payload["warnings_json"] = list(warnings)
            repo.add_sync_run(sync_payload)
            session.commit()
            report["database_counts"] = repo.counts(portfolio_id)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        if report_file is not None:
            write_json_atomic(report_file, report)
        return report

    def validate(self, portfolio_id: str) -> dict:
        session = self.session_factory()
        try:
            counts = PortfolioManagementRepository(session).counts(portfolio_id)
            return {"portfolio_id": portfolio_id, "status": "AVAILABLE" if counts["accounts"] else "MISSING", "counts": counts}
        finally:
            session.close()

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from trading_ai.portfolio_management.database_models import (
    PortfolioAccountModel,
    PortfolioAuditModel,
    PortfolioCashLedgerModel,
    PortfolioPositionModel,
    PortfolioSnapshotModel,
    PortfolioSyncRunModel,
)


class PortfolioManagementRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_account(self, payload: dict) -> None:
        values = dict(payload)
        values["metadata_json"] = values.pop("metadata", {})
        self._upsert(PortfolioAccountModel, values["portfolio_id"], values)

    def upsert_position(self, payload: dict) -> None:
        values = dict(payload)
        values["metadata_json"] = values.pop("metadata", {})
        self._upsert(PortfolioPositionModel, values["position_id"], values)

    def upsert_ledger_entry(self, payload: dict) -> None:
        self._upsert(PortfolioCashLedgerModel, payload["entry_id"], dict(payload))

    def upsert_snapshot(self, payload: dict) -> None:
        values = {
            "snapshot_id": payload["snapshot_id"],
            "portfolio_id": payload["portfolio_id"],
            "generated_at": payload["generated_at"],
            "registry_fingerprint": payload["registry_fingerprint"],
            "registry_json": payload["registry"],
            "exposure_json": payload["exposure"],
            "warnings_json": payload.get("warnings", []),
        }
        self._upsert(PortfolioSnapshotModel, values["snapshot_id"], values)

    def upsert_audit_record(self, payload: dict) -> None:
        values = dict(payload)
        values["metadata_json"] = values.pop("metadata", {})
        self._upsert(PortfolioAuditModel, values["audit_id"], values)

    def add_sync_run(self, payload: dict) -> None:
        self._upsert(PortfolioSyncRunModel, payload["sync_id"], payload)

    def counts(self, portfolio_id: str) -> dict[str, int]:
        return {
            "accounts": len(self.session.scalars(select(PortfolioAccountModel).where(PortfolioAccountModel.portfolio_id == portfolio_id)).all()),
            "positions": len(self.session.scalars(select(PortfolioPositionModel).where(PortfolioPositionModel.portfolio_id == portfolio_id)).all()),
            "ledger_entries": len(self.session.scalars(select(PortfolioCashLedgerModel).where(PortfolioCashLedgerModel.portfolio_id == portfolio_id)).all()),
            "snapshots": len(self.session.scalars(select(PortfolioSnapshotModel).where(PortfolioSnapshotModel.portfolio_id == portfolio_id)).all()),
            "audit_records": len(self.session.scalars(select(PortfolioAuditModel).where(PortfolioAuditModel.portfolio_id == portfolio_id)).all()),
            "sync_runs": len(self.session.scalars(select(PortfolioSyncRunModel).where(PortfolioSyncRunModel.portfolio_id == portfolio_id)).all()),
        }

    def _upsert(self, model, primary_key: str, values: dict) -> None:
        instance = self.session.get(model, primary_key)
        if instance is None:
            self.session.add(model(**values))
            return
        for key, value in values.items():
            setattr(instance, key, value)

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, func, select

from trading_ai.database.session import SessionLocal
from trading_ai.opex_intelligence.models import (
    OpexForecastOutcomeModel,
    OpexForecastPublicationModel,
    OpexForecastSnapshotModel,
)
from trading_ai.performance_learning.models import (
    PredictionOutcomeModel,
    PredictionRegistryModel,
)


VERSION = "M71.4-OPEX-HISTORICAL-CLEANUP-1.0"
CONFIRMATION = "PURGE_NONAUTHORITATIVE_OPEX_DUPLICATES"


def _plan(session) -> dict:
    publication = session.scalar(
        select(OpexForecastPublicationModel).where(
            OpexForecastPublicationModel.publication_name
            == "current_opex_intelligence"
        )
    )
    current_ids = set(
        ((publication.payload_json or {}).get("forecast_ids") or [])
        if publication
        else []
    )
    snapshots = list(
        session.scalars(
            select(OpexForecastSnapshotModel).order_by(
                OpexForecastSnapshotModel.symbol,
                OpexForecastSnapshotModel.expiration,
                OpexForecastSnapshotModel.source_as_of_date,
                OpexForecastSnapshotModel.forecast_timestamp,
            )
        )
    )
    groups: dict[tuple[str, str, str], list[OpexForecastSnapshotModel]] = defaultdict(list)
    for row in snapshots:
        groups[(row.source_as_of_date, row.symbol, row.expiration)].append(row)

    keep_ids = set(current_ids)
    duplicate_groups = 0
    for rows in groups.values():
        if len(rows) > 1:
            duplicate_groups += 1
        current = [row for row in rows if row.forecast_id in current_ids]
        keeper = max(
            current or rows,
            key=lambda row: row.forecast_timestamp,
        )
        keep_ids.add(keeper.forecast_id)

    delete_ids = sorted(
        row.forecast_id
        for row in snapshots
        if row.forecast_id not in keep_ids
    )
    legacy_invalid_outcomes = list(
        session.scalars(
            select(OpexForecastOutcomeModel).where(
                OpexForecastOutcomeModel.settlement_source.is_(None)
            )
        )
    )
    prediction_rows = list(
        session.scalars(
            select(PredictionRegistryModel).where(
                PredictionRegistryModel.source_id.in_(
                    [f"OPEX:{forecast_id}" for forecast_id in delete_ids]
                )
            )
        )
    ) if delete_ids else []
    prediction_ids = [row.prediction_id for row in prediction_rows]
    outcome_rows_for_deleted_forecasts = list(
        session.scalars(
            select(OpexForecastOutcomeModel).where(
                OpexForecastOutcomeModel.forecast_id.in_(delete_ids)
            )
        )
    ) if delete_ids else []
    manifest = {
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "publication_id": publication.publication_id if publication else None,
        "current_authority_ids": sorted(current_ids),
        "before": {
            "forecast_snapshots": len(snapshots),
            "source_symbol_expiration_groups": len(groups),
            "duplicate_groups": duplicate_groups,
        },
        "planned": {
            "retained_forecasts": len(keep_ids),
            "deleted_forecasts": len(delete_ids),
            "deleted_forecast_outcomes": len(outcome_rows_for_deleted_forecasts),
            "deleted_legacy_close_based_outcomes": len(legacy_invalid_outcomes),
            "deleted_prediction_registry_rows": len(prediction_rows),
            "deleted_prediction_outcomes": None,
        },
        "delete_forecast_ids": delete_ids,
        "prediction_ids": prediction_ids,
        "authority_preservation": {
            "required": len(current_ids),
            "retained": len(current_ids & keep_ids),
            "status": "PASSED" if publication is not None and current_ids and current_ids <= keep_ids else "FAILED",
        },
    }
    return manifest


def _execute(session, manifest: dict) -> dict:
    if manifest["authority_preservation"]["status"] != "PASSED":
        raise RuntimeError("Current OPEX authority preservation failed")
    delete_ids = list(manifest["delete_forecast_ids"])
    prediction_ids = list(manifest["prediction_ids"])
    deleted_prediction_outcomes = 0
    if prediction_ids:
        result = session.execute(
            delete(PredictionOutcomeModel).where(
                PredictionOutcomeModel.prediction_id.in_(prediction_ids)
            )
        )
        deleted_prediction_outcomes = int(result.rowcount or 0)
        session.execute(
            delete(PredictionRegistryModel).where(
                PredictionRegistryModel.prediction_id.in_(prediction_ids)
            )
        )
    session.execute(
        delete(OpexForecastOutcomeModel).where(
            OpexForecastOutcomeModel.settlement_source.is_(None)
        )
    )
    if delete_ids:
        session.execute(
            delete(OpexForecastOutcomeModel).where(
                OpexForecastOutcomeModel.forecast_id.in_(delete_ids)
            )
        )
        session.execute(
            delete(OpexForecastSnapshotModel).where(
                OpexForecastSnapshotModel.forecast_id.in_(delete_ids)
            )
        )
    session.commit()
    remaining = session.scalar(
        select(func.count()).select_from(OpexForecastSnapshotModel)
    )
    manifest["executed_at"] = datetime.now(timezone.utc).isoformat()
    manifest["status"] = "EXECUTED"
    manifest["after"] = {"forecast_snapshots": int(remaining or 0)}
    manifest["planned"]["deleted_prediction_outcomes"] = deleted_prediction_outcomes
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preflight or execute bounded M71.4 OPEX historical cleanup."
    )
    parser.add_argument("--mode", choices=("preflight", "execute"), default="preflight")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--output", default="m71_4_opex_cleanup_manifest.json")
    args = parser.parse_args()

    with SessionLocal() as session:
        manifest = _plan(session)
        if args.mode == "execute":
            if args.confirm != CONFIRMATION:
                raise SystemExit(
                    f"Execution requires --confirm {CONFIRMATION}"
                )
            manifest = _execute(session, manifest)
        else:
            manifest["status"] = "PREFLIGHT"
            session.rollback()

    Path(args.output).write_text(
        json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

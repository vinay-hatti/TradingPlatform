from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DealerScannerLoadResult:
    status: str
    snapshot: object | None = None
    snapshot_age_days: int | None = None
    error: str | None = None


class DealerPositioningScannerRepository:
    """Read-only scanner access to the latest persisted Milestone 44 snapshot."""

    def load_latest(
        self,
        symbol: str,
        scan_date: date,
        maximum_age_days: int = 1,
    ) -> DealerScannerLoadResult:
        try:
            from sqlalchemy import select
            from trading_ai.database.session import create_session
            from trading_ai.institutional_market_structure.database_models import (
                DealerPositionSnapshotModel,
            )
            from trading_ai.institutional_market_structure.serialization import (
                snapshot_from_dict,
            )
            import json

            with create_session() as session:
                row = session.scalar(
                    select(DealerPositionSnapshotModel)
                    .where(
                        DealerPositionSnapshotModel.symbol == symbol.upper(),
                        DealerPositionSnapshotModel.quote_date <= scan_date,
                    )
                    .order_by(DealerPositionSnapshotModel.quote_date.desc())
                    .limit(1)
                )
                if row is None:
                    return DealerScannerLoadResult(status="MISSING")

                age_days = (scan_date - row.quote_date).days
                if age_days > int(maximum_age_days):
                    return DealerScannerLoadResult(
                        status="STALE",
                        snapshot_age_days=age_days,
                        error=(
                            f"Dealer snapshot {row.quote_date} is {age_days} days old; "
                            f"maximum allowed is {maximum_age_days}."
                        ),
                    )

                snapshot = snapshot_from_dict(json.loads(row.payload_json))
                return DealerScannerLoadResult(
                    status="FRESH",
                    snapshot=snapshot,
                    snapshot_age_days=age_days,
                )
        except Exception as exc:  # scanner must degrade neutrally
            return DealerScannerLoadResult(
                status="ERROR",
                error=f"{type(exc).__name__}: {exc}",
            )

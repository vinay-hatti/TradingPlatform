from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from sqlalchemy import func, select

from trading_ai.database.session import create_session
from trading_ai.institutional_market_structure.contracts import DealerPositioningPolicy
from trading_ai.institutional_market_structure.database_models import DealerPositionSnapshotModel
from trading_ai.institutional_market_structure.refresh import (
    DealerPositionRefreshOrchestrator,
    write_refresh_profile,
)


def parse_symbols(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(dict.fromkeys(x.strip().upper() for x in value.split(",") if x.strip()))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild dealer-positioning snapshots using corrected gamma-flip signs."
    )
    parser.add_argument("--as-of", help="Snapshot as-of date; defaults to latest persisted dealer date.")
    parser.add_argument("--symbols", help="Optional comma-separated symbol subset.")
    parser.add_argument("--output-dir", default="reports/m44")
    parser.add_argument(
        "--report",
        default="reports/market_ingestion/dealer_gamma_flip_rebuild_latest.json",
    )
    parser.add_argument("--maximum-snapshot-age-days", type=int, default=7)
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()

    requested = parse_symbols(args.symbols)
    with create_session() as session:
        latest = session.scalar(select(func.max(DealerPositionSnapshotModel.as_of_date)))
        as_of = date.fromisoformat(args.as_of) if args.as_of else latest
        if as_of is None:
            raise SystemExit("No dealer_position_snapshot rows exist and --as-of was not supplied.")
        if not requested:
            requested = tuple(
                session.scalars(
                    select(DealerPositionSnapshotModel.symbol)
                    .where(DealerPositionSnapshotModel.as_of_date == as_of)
                    .order_by(DealerPositionSnapshotModel.symbol)
                ).all()
            )

    if not requested:
        raise SystemExit(f"No dealer symbols found for {as_of}.")

    policy = DealerPositioningPolicy(
        dealer_sign_convention="street_proxy",
        maximum_snapshot_age_days=args.maximum_snapshot_age_days,
    )
    profile = DealerPositionRefreshOrchestrator(
        policy,
        output_dir=Path(args.output_dir),
        write_reports=False,
    ).run(requested, as_of, continue_on_error=not args.fail_fast)
    target = write_refresh_profile(profile, args.report)
    print(json.dumps({
        "as_of_date": profile.as_of_date,
        "requested_symbols": profile.requested_symbols,
        "refreshed_symbols": profile.refreshed_symbols,
        "failed_symbols": profile.failed_symbols,
        "skipped_symbols": profile.skipped_symbols,
        "report": str(target),
    }, indent=2))


if __name__ == "__main__":
    main()
